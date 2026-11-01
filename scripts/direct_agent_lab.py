"""Direct GitOps deployment to isolated Ignition 8.3 TEST Agent.

Fail closed by default: secure Agent HTTPS scan and independently checked runtime
required. This is a candidate, NOT proof of a completed deployment.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tarfile
import time
import uuid
import zipfile
from urllib.request import Request, urlopen
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "DeploymentSmokeTest"
AGENT = "ignition-eam-agent"
CTRL = "ignition-eam-controller"
DATA = "/usr/local/bin/ignition/data"
SOURCE = ROOT / "ignition-project" / PROJECT
REPORT = ROOT / "evidence/direct-agent.json"


def check_env():
    if os.getenv("IGNITION_LAB_ONLY") != "YES":
        raise RuntimeError("HOLD: TEST-only gate")
    if os.getenv("IGNITION_AGENT_CONTAINER") != AGENT or os.getenv("IGNITION_CONTROLLER_CONTAINER") != CTRL:
        raise RuntimeError("HOLD: Docker allowlist")
    sha = os.getenv("RELEASE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("HOLD: invalid release SHA")
    if not SOURCE.joinpath("project.json").is_file() or any(p.is_symlink() for p in SOURCE.rglob("*")):
        raise RuntimeError("HOLD: invalid native project")
    manifest = json.loads((ROOT / "manifests/ignition-test.json").read_text())
    if manifest.get("production_approved") is not False or manifest.get("project") != PROJECT:
        raise RuntimeError("HOLD: manifest not TEST-only")
    url = os.getenv("IGNITION_AGENT_SCAN_URL", "")
    if url != "https://localhost:9243/data/api/v1/scan/projects":
        raise RuntimeError("HOLD: expected isolated Agent HTTPS scan at localhost:9243")
    ca = Path(os.getenv("IGNITION_AGENT_CA_FILE", "")).expanduser()
    if not ca.is_file():
        raise RuntimeError("HOLD: Agent trusted CA certificate missing")
    if not os.getenv("IGNITION_AGENT_API_TOKEN"):
        raise RuntimeError("HOLD: Agent API token missing")
    backups = Path(os.getenv("IGNITION_BACKUP_DIR", "")).expanduser().resolve()
    if not backups.is_dir() or backups == ROOT or ROOT in backups.parents:
        raise RuntimeError("HOLD: backup directory missing/unsafe")
    return sha, url, ca, backups


def run(*args, stdout=None):
    return subprocess.run(args, check=True, stdout=stdout, stderr=subprocess.PIPE)


def exists(path):
    proc = subprocess.run(["docker", "exec", AGENT, "test", "-e", path], stdout=subprocess.DEVNULL)
    if proc.returncode not in (0, 1):
        raise RuntimeError("Cannot check Agent path")
    return proc.returncode == 0


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def remote_hashes(files, base):
    result = {}
    for rel in files:
        value = subprocess.check_output(["docker", "exec", AGENT, "sha256sum", base + "/" + rel], text=True)
        result[rel] = value.split()[0]
    return result



def version_in_tree(data):
    versions = []
    def visit(obj):
        if isinstance(obj, dict):
            if obj.get("meta", {}).get("name") == "BuildVersion":
                versions.append(obj.get("props", {}).get("text"))
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)
    visit(data)
    if len(versions) != 1 or not re.fullmatch(r"SMOKE VERSION V[0-9]+", str(versions[0])):
        raise RuntimeError("HOLD: invalid Perspective BuildVersion")
    return versions[0]


def scan_api(url, token, context, method="GET"):
    req = Request(url, method=method, data=b"" if method == "POST" else None,
                  headers={"X-Ignition-API-Token": token})
    with urlopen(req, timeout=30, context=context) as response:
        if response.status != 200:
            raise RuntimeError("FAIL: Agent scan API did not return HTTP 200")
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get("scanActive"), bool):
        raise RuntimeError("FAIL: malformed Agent scan response")
    return data


def wait_scan(url, token, context, baseline_timestamp=None):
    """Never treat a pre-existing idle scan as completion of this release."""
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        data = scan_api(url, token, context)
        timestamp = data.get("lastScanTimestamp")
        advanced = (baseline_timestamp is None or
                    (isinstance(timestamp, (int, float)) and
                     timestamp > baseline_timestamp))
        if data["scanActive"] is False and advanced:
            return data
        time.sleep(2)
    raise RuntimeError("FAIL: project scan did not complete with a new timestamp")


def make_browser():
    """Choose a browser installed on the runner, not the developer's workstation."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions

    choice = os.getenv("IGNITION_E2E_BROWSER", "auto").strip().lower()
    aliases = {"chromium": "chrome", "google-chrome": "chrome", "msedge": "edge"}
    choice = aliases.get(choice, choice)
    if choice not in ("auto", "chrome", "edge", "firefox"):
        raise RuntimeError("HOLD: unsupported IGNITION_E2E_BROWSER")
    options_by_name = {
        "chrome": (ChromeOptions, webdriver.Chrome),
        "edge": (EdgeOptions, webdriver.Edge),
        "firefox": (FirefoxOptions, webdriver.Firefox),
    }
    # Try supported browsers without assuming Firefox or Linux-specific paths.
    order = ("chrome", "edge", "firefox") if choice == "auto" else (choice,)
    errors = {}
    for name in order:
        option_type, factory = options_by_name[name]
        opts = option_type()
        opts.add_argument("--headless" if name != "firefox" else "-headless")
        if name in ("chrome", "edge"):
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
        opts.accept_insecure_certs = False
        try:
            return name, factory(options=opts)
        except Exception as exc:
            errors[name] = type(exc).__name__ + ": " + str(exc)[:220]
    raise RuntimeError("HOLD: no browser WebDriver could start: " + json.dumps(errors))


def browser_version(expected):
    # Real rendered-client proof; browser is selected on the runner.
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    browser, driver = make_browser()
    try:
        driver.set_page_load_timeout(40)
        driver.get("http://localhost:9288/data/perspective/client/DeploymentSmokeTest")
        def visible(d):
            return any(e.is_displayed() for e in d.find_elements(
                By.XPATH, "//*[normalize-space(text())='%s']" % expected))
        def reload_until_visible(d):
            if visible(d):
                return True
            d.refresh()
            return False
        WebDriverWait(driver, 60, poll_frequency=3).until(reload_until_visible)
        return {"browser": browser, "verified_visible_text": expected,
                "browser_title": driver.title}
    finally:
        driver.quit()


def verify_full_gateway_backup():
    value = os.getenv("IGNITION_AGENT_GWBK", "")
    path = Path(value).expanduser().resolve() if value else Path("/nonexistent")
    if not path.is_file() or not path.suffix == ".gwbk" or not zipfile.is_zipfile(path):
        raise RuntimeError("HOLD: full Agent Gateway backup (.gwbk) required")
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) < 10 or archive.testzip() is not None:
            raise RuntimeError("HOLD: Gateway backup ZIP integrity check failed")
    return path


def main():
    sha, url, ca, backups = check_env()
    gateway_backup = verify_full_gateway_backup()
    context = ssl.create_default_context(cafile=str(ca))
    token = os.environ["IGNITION_AGENT_API_TOKEN"]
    # Authenticated Agent API and both containers must pass before any mutation.
    initial_scan = scan_api(url, token, context)
    if initial_scan["scanActive"]:
        raise RuntimeError("HOLD: Agent project scan already active")
    if not isinstance(initial_scan.get("lastScanTimestamp"), (int, float)):
        raise RuntimeError("HOLD: Agent scan baseline timestamp missing")
    # Qualify the browser BEFORE changing any Gateway project files.
    # Failure here is a preflight HOLD, not a deployment requiring rollback.
    browser_name, browser_probe = make_browser()
    try:
        browser_probe.set_page_load_timeout(15)
    finally:
        browser_probe.quit()

    for container in (AGENT, CTRL):
        state = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container], text=True
        ).strip()
        if state != "healthy":
            raise RuntimeError("HOLD: unhealthy " + container)
    files = {p.relative_to(SOURCE).as_posix(): digest(p) for p in SOURCE.rglob("*") if p.is_file()}
    if len(files) < 2:
        raise RuntimeError("HOLD: unexpectedly small native project")
    expected = version_in_tree(json.loads((SOURCE / "com.inductiveautomation.perspective/views/Main/view.json").read_text()))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
    backup = backups / (stamp + "-" + sha[:12] + "-agent-direct")
    backup.mkdir(mode=0o700)
    dst = DATA + "/projects/" + PROJECT
    tmp = DATA + "/projects/.direct-stage-" + stamp
    prior = DATA + "/projects/.direct-prior-" + stamp
    report = {"sha": sha, "project": PROJECT, "mode": "DIRECT_AGENT_TEST",
              "expected": expected, "backup": str(backup),
              "full_gateway_backup": str(gateway_backup), "e2e": "HOLD"}
    REPORT.parent.mkdir(exist_ok=True)
    swapped = False
    old_version = None
    old_hashes = None
    try:
        # Preserve official full Gateway backup and container project trees first.
        shutil.copy2(gateway_backup, backup / "agent-gateway-before-release.gwbk")
        for container in (CTRL, AGENT):
            archive = backup / (container + "-projects.tar")
            with archive.open("wb") as f:
                run("docker", "exec", container, "tar", "-cf", "-", "-C", DATA, "projects", stdout=f)
            with tarfile.open(archive, "r:") as tf:
                if not tf.getmembers():
                    raise RuntimeError("FAIL: empty project backup " + container)
        report["project_backups"] = "PASS"
        if not exists(dst) or exists(tmp) or exists(prior):
            raise RuntimeError("HOLD: missing target or staging collision")
        old_json = subprocess.check_output(["docker", "exec", AGENT, "cat",
            dst + "/com.inductiveautomation.perspective/views/Main/view.json"], text=True)
        old_version = version_in_tree(json.loads(old_json))
        report["previous_version"] = old_version
        report["previous_browser"] = browser_version(old_version)
        report["preflight_browser"] = browser_name
        old_hashes = remote_hashes(files, dst)
        listed = subprocess.check_output(["docker", "exec", AGENT, "find",
            dst, "-type", "f", "-printf", "%P\\n"], text=True).splitlines()
        if set(listed) != set(files):
            raise RuntimeError("HOLD: unmanaged Agent files or deletions")
        run("docker", "cp", str(SOURCE), AGENT + ":" + tmp)
        run("docker", "exec", "-u", "0", AGENT, "chown", "-R", "ignition:ignition", tmp)
        if remote_hashes(files, tmp) != files:
            raise RuntimeError("FAIL: staging content mismatch")
        run("docker", "exec", AGENT, "mv", dst, prior)
        swapped = True
        run("docker", "exec", AGENT, "mv", tmp, dst)
        if remote_hashes(files, dst) != files:
            raise RuntimeError("FAIL: on-disk release hash mismatch")
        report["agent_files"] = "MATCH"
        report["scan_request"] = scan_api(url, token, context, method="POST")
        report["scan_final"] = wait_scan(
            url, token, context, baseline_timestamp=initial_scan["lastScanTimestamp"])
        # Only the independently rendered Perspective version authorizes PASS.
        report["runtime"] = browser_version(expected)
        report["e2e"] = "PASS"
        # Project tar and full Gateway backup remain available after success.
        run("docker", "exec", AGENT, "rm", "-rf", prior)
    except Exception as exc:
        report["error"] = str(exc)
        if swapped:
            try:
                failed = DATA + "/projects/.direct-failed-" + stamp
                if exists(dst):
                    run("docker", "exec", AGENT, "mv", dst, failed)
                if exists(prior):
                    run("docker", "exec", AGENT, "mv", prior, dst)
                if old_hashes is None or remote_hashes(files, dst) != old_hashes:
                    raise RuntimeError("FAIL: rollback file hashes differ from pre-deployment state")
                rollback_baseline = scan_api(url, token, context)
                scan_api(url, token, context, method="POST")
                report["rollback_scan"] = wait_scan(
                    url, token, context,
                    baseline_timestamp=rollback_baseline.get("lastScanTimestamp"))
                report["rollback_runtime"] = browser_version(old_version)
                report["rollback"] = "VERIFIED"
            except Exception as rollback_exc:
                report["rollback"] = "FAILED_ENGINEER_REQUIRED"
                report["rollback_error"] = str(rollback_exc)
        raise
    finally:
        # Remove only the unused pre-swap staging directory. On failure, preserve
        # prior/failed directories and the backup for forensic recovery.
        if not swapped and exists(tmp):
            run("docker", "exec", AGENT, "rm", "-rf", tmp)
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        (backup / "release-evidence.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
