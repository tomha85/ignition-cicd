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
import tempfile
import time
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


def main():
    sha, url, ca, backups = check_env()
    context = ssl.create_default_context(cafile=str(ca))
    # Validate Agent TLS endpoint BEFORE filesystem writes. Never fall back to HTTP.
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=15, context=context):
            pass
    except Exception as e:
        # 401/403/405 are acceptable indications of TLS connectivity, not scan authorization.
        from urllib.error import HTTPError
        if not isinstance(e, HTTPError) or e.code not in (401, 403, 405):
            raise RuntimeError("HOLD: Agent HTTPS preflight failed: " + str(e))
    for container in (AGENT, CTRL):
        state = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Health.Status}}", container], text=True).strip()
        if state != "healthy":
            raise RuntimeError("HOLD: unhealthy " + container)
    # No mutation until a separately qualified runtime verifier is available.
    # Supplying a commit SHA is not runtime proof.
    if os.getenv("IGNITION_DIRECT_RUNTIME_VERIFIER_QUALIFIED") != "true":
        raise RuntimeError("HOLD: direct Agent runtime verifier is not qualified")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / (stamp + "-" + sha[:12] + "-agent-direct")
    backup.mkdir(mode=0o700)
    report = {"sha": sha, "project": PROJECT, "mode": "DIRECT_AGENT_TEST", "backup": str(backup), "e2e": "HOLD"}
    REPORT.parent.mkdir(exist_ok=True)
    files = {p.relative_to(SOURCE).as_posix(): digest(p) for p in SOURCE.rglob("*") if p.is_file()}
    dst = DATA + "/projects/" + PROJECT
    tmp = DATA + "/projects/.direct-stage-" + sha[:12]
    prior = DATA + "/projects/.direct-prior-" + sha[:12]
    try:
        # Filesystem backups are NOT substitutes for full Gateway .gwbk backups.
        for c in (CTRL, AGENT):
            path = backup / (c + "-projects.tar")
            with path.open("wb") as f:
                run("docker", "exec", c, "tar", "-cf", "-", "-C", DATA, "projects", stdout=f)
            with tarfile.open(path, "r:") as tf:
                if not tf.getmembers():
                    raise RuntimeError("HOLD: empty backup " + c)
        report["project_backups"] = "VERIFIED"
        # Refuse unmanaged local resources or collision with previous interrupted attempt.
        if exists(tmp) or exists(prior):
            raise RuntimeError("HOLD: staging/prior path exists")
        if exists(dst):
            listed = subprocess.check_output(["docker", "exec", AGENT, "find", dst, "-type", "f", "-printf", "%P\\n"], text=True).splitlines()
            if set(listed) != set(files):
                raise RuntimeError("HOLD: unmanaged Agent files or deletions")
        run("docker", "cp", str(SOURCE), AGENT + ":" + tmp)
        run("docker", "exec", "-u", "0", AGENT, "chown", "-R", "ignition:ignition", tmp)
        if remote_hashes(files, tmp) != files:
            raise RuntimeError("HOLD: staging content mismatch")
        if exists(dst):
            run("docker", "exec", AGENT, "mv", dst, prior)
        run("docker", "exec", AGENT, "mv", tmp, dst)
        if remote_hashes(files, dst) != files:
            raise RuntimeError("FAIL: Agent on-disk release mismatch")
        report["agent_files"] = "MATCH"
        token = os.environ["IGNITION_AGENT_API_TOKEN"]
        scan = Request(url, method="POST", data=b"", headers={"X-Ignition-API-Token": token})
        with urlopen(scan, timeout=30, context=context) as response:
            if response.status != 200:
                raise RuntimeError("HOLD: scan did not return expected HTTP 200")
            body = json.load(response)
        report["scan_response"] = body
        if not isinstance(body, dict):
            raise RuntimeError("HOLD: scan response not JSON object")
        # A 200 + file hashes is not proof Gateway loaded the new Perspective resources.
        # Independently implement/qualify authenticated runtime view-version test before PASS.
        report["scan"] = "REQUEST_ACCEPTED_NOT_RUNTIME_VERIFIED"
        raise RuntimeError("HOLD: native Perspective runtime verification not qualified")
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
