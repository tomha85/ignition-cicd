#!/usr/bin/env python3
"""Manifest-validated, owner-approved, isolated TEST Controller staging.

No EAM Agent Send Project task and NO production operations.
Only a target in the reviewed TEST registry may authorize a Controller stage.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError, load_factory, plan_release, validate_catalog
from framework.deployment.planner import resolve_project_gateway
from framework.security.policies import resolve_controller_stage_target
from scripts.verify_stage_approval import verify as verify_github_approval
from scripts.eam_stamp_project_description import stamp as stamp_description

DATA = "/usr/local/bin/ignition/data"
REPORT = ROOT / "evidence/selected-controller-stage.json"
PROJECT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")


def require(condition, reason):
    if not condition:
        raise FrameworkError("HOLD: " + reason)


def output(*args):
    return subprocess.check_output(args, stderr=subprocess.PIPE, text=True).strip()


def execute(*args, stdout=None):
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, stdout=stdout)


def exists(container, path):
    p = subprocess.run(["docker", "exec", container, "test", "-e", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    require(p.returncode in (0, 1), "cannot inspect Controller path")
    return p.returncode == 0


def hashes_equal(container, base, expected):
    # A passing subset of file hashes is not enough: unexpected files or
    # symlinks must also invalidate the installed project tree.
    actual = output("docker", "exec", container, "find", base,
                    "(", "-type", "f", "-o", "-type", "l", ")",
                    "-printf", "%P\\n")
    found = set(actual.splitlines()) if actual else set()
    require(found == set(expected),
            "Controller project tree differs from immutable native source")
    for rel, checksum in expected.items():
        got = output("docker", "exec", container, "sha256sum",
                     base + "/" + rel).split()[0]
        require(got == checksum, "Controller file hash mismatch: " + rel)


def controller_scan(url, token, ctx):
    headers = {"X-Ignition-API-Token": token}
    with urlopen(Request(url, data=b"", method="POST", headers=headers),
                 context=ctx, timeout=30) as response:
        require(response.status == 200, "Controller scan failed")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        with urlopen(Request(url, headers=headers),
                     context=ctx, timeout=30) as response:
            state = json.load(response)
        if state.get("scanActive") is False:
            return
        time.sleep(2)
    raise FrameworkError("HOLD: Controller scan remained active")


def prepare(factory, gateway, project, sha):
    """Verify immutable source and target registration without any Gateway writes."""
    require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)), "invalid full Git SHA")
    require(bool(PROJECT_RE.fullmatch(project)), "invalid project name")
    validate_catalog(ROOT / "factories")
    require(resolve_project_gateway(ROOT, factory, project) == gateway,
            "project/Gateway association does not match unique manifest mapping")
    plan = plan_release(ROOT / "factories", factory, gateway, "test", sha)
    found = [p for p in plan["projects"] if p["name"] == project]
    require(len(found) == 1, "project missing from validated native manifest")
    target = resolve_controller_stage_target(ROOT, factory, gateway, project)
    manifest = load_factory(ROOT / "factories", factory)
    selected = next(g for g in manifest["gateways"] if g["gateway_id"] == gateway)
    record = next(p for p in selected["projects"] if p["name"] == project)
    # Source path has already been validated by load_factory. Confirm resolved
    # source is owned by this factory and is the selected native project.
    factory_dir = (ROOT / "factories" / factory).resolve()
    source = (factory_dir / record["source"]).resolve()
    require(source.is_relative_to(factory_dir / "projects") and source.is_dir(),
            "source outside factory projects")
    return target, source, found[0]["sha256"]


def prepare_stamped_copy(source, source_hashes, copy_dir, factory, sha, run_id):
    """Produce a verified TEST-only copy; never mutate the Git checkout."""
    require(copy_dir.parent.is_dir() and not copy_dir.exists(),
            "unsafe staging copy path")
    require(bool(re.fullmatch(r"[0-9]{1,20}", run_id)),
            "missing/invalid GitHub run ID")
    # Do not follow symlinks while preparing the native project.
    require(not any(p.is_symlink() for p in source.rglob("*")),
            "symlink in source project")
    source_files = {p.relative_to(source).as_posix(): p
                    for p in source.rglob("*") if p.is_file()}
    require(set(source_files) == set(source_hashes),
            "source tree differs from immutable manifest")
    for name, src in source_files.items():
        require(hashlib.sha256(src.read_bytes()).hexdigest() == source_hashes[name],
                "source hash mismatch before description stamping: " + name)
    shutil.copytree(source, copy_dir, symlinks=True)
    metadata = stamp_description(copy_dir, factory, sha, run_id)
    require(metadata["project"] == source.name, "description project mismatch")
    expected = dict(source_hashes)
    expected["project.json"] = hashlib.sha256(
        (copy_dir / "project.json").read_bytes()).hexdigest()
    require({p.relative_to(copy_dir).as_posix()
             for p in copy_dir.rglob("*") if p.is_file()} == set(expected),
            "stamped project file set changed")
    for name, digest in expected.items():
        require(hashlib.sha256((copy_dir / name).read_bytes()).hexdigest() == digest,
                "stamped file hash mismatch: " + name)
    return expected, metadata


def stage(factory, gateway, project, sha):
    target, source, expected = prepare(factory, gateway, project, sha)
    report = {
        "status": "HOLD", "mode": "ISOLATED_TEST_CONTROLLER_ONLY",
        "sha": sha, "factory_id": factory, "gateway_id": gateway,
        "project": project, "target_id": target["target_id"],
        "eam_send_project": "NOT_RUN", "agent_verification": "NOT_RUN",
        "browser_render": "NOT_TESTED", "fat": "NOT_TESTED",
        "production": "FORBIDDEN",
    }
    require(os.getenv("IGNITION_TEST_STAGE_CONFIRM") == "ISOLATED_TEST_ONLY",
            "explicit isolated TEST stage confirmation missing")
    require(os.getenv("GITHUB_REPOSITORY") == "tomha85/ignition-cicd",
            "wrong GitHub repository")
    require(os.getenv("GITHUB_REF") == "refs/heads/main", "only main can stage")
    require(os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch",
            "only manually reviewed TEST workflow can stage")
    require(os.getenv("GITHUB_SHA") == sha, "release SHA mismatch")
    require(output("git", "rev-parse", "HEAD") == sha,
            "checkout must equal reviewed immutable release SHA")
    approval = verify_github_approval(os.environ, os.getenv("GH_APPROVAL_READ_TOKEN"))
    report["approval"] = approval["status"]
    controller = target["controller_id"]
    agent = target["agent_id"]
    require(os.getenv("IGNITION_CONTROLLER_CONTAINER") == controller,
            "actual LAB Controller does not match registered TEST target")
    require(os.getenv("IGNITION_AGENT_CONTAINER") == agent,
            "actual LAB Agent does not match registered TEST target")

    backup_dir = os.getenv("IGNITION_BACKUP_DIR")
    require(bool(backup_dir), "backup directory not configured")
    backup_root = Path(backup_dir).expanduser().resolve()
    require(backup_root.is_dir() and ROOT not in backup_root.parents
            and backup_root != ROOT and not backup_root.is_symlink(),
            "unsafe/missing backup directory")
    ca_file = Path(os.getenv("IGNITION_CONTROLLER_CA_FILE") or "/invalid")
    token = os.getenv("IGNITION_CONTROLLER_API_TOKEN")
    require(bool(token) and ca_file.is_file() and not ca_file.is_symlink(),
            "Controller HTTPS API credentials/CA missing")
    ssl_context = ssl.create_default_context(cafile=str(ca_file))
    for container in (controller, agent):
        require(output("docker", "inspect", "--format", "{{.State.Running}}",
                       container) == "true", "TEST container unavailable")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    backup = backup_root / ("reviewed-test-" + stamp)
    backup.mkdir(mode=0o700)
    report["backup"] = str(backup)
    dst = DATA + "/projects/" + project
    temporary = DATA + "/.reviewed-stage-" + stamp
    previous = DATA + "/.reviewed-prior-" + stamp
    rejected = DATA + "/.reviewed-rejected-" + stamp
    created, replaced = False, False
    try:
        for container in (controller, agent):
            archive = backup / (container + "-projects.tar")
            with archive.open("wb") as fd:
                execute("docker", "exec", container, "tar", "-cf", "-",
                        "-C", DATA, "projects", stdout=fd)
            with tarfile.open(archive) as tf:
                require(bool(tf.getmembers()), "empty project backup")
        report["backup_verified"] = True
        # Stage a source-verified, description-stamped copy outside the Git checkout.
        # The stamped project.json has its own expected hash; all other files must
        # remain byte-identical to the approved release.
        staged_source = backup / "staged-source" / project
        staged_source.parent.mkdir(mode=0o700)
        expected, description = prepare_stamped_copy(
            source, expected, staged_source, factory, sha,
            os.getenv("GITHUB_RUN_ID", ""))
        report["description_stamp"] = description
        report["description_status"] = "TEST_CONTROLLER_STAGED_NOT_AGENT_VERIFIED"
        require(not any(exists(controller, x) for x in (temporary, previous, rejected)),
                "staging or backup path collision")
        installed = exists(controller, dst)
        identical = False
        if installed:
            try:
                hashes_equal(controller, dst, expected)
                identical = True
            except (FrameworkError, subprocess.CalledProcessError):
                identical = False
        if identical:
            report["staging"] = "PASS_ALREADY_IDENTICAL"
        else:
            execute("docker", "cp", str(staged_source), controller + ":" + temporary)
            execute("docker", "exec", "-u", "0", controller, "chown",
                    "-R", "ignition:ignition", temporary)
            hashes_equal(controller, temporary, expected)
            if installed:
                require(exists(controller, dst), "Controller project disappeared")
                execute("docker", "exec", controller, "mv", dst, previous)
                replaced = True
            else:
                require(not exists(controller, dst), "unexpected project appeared")
            execute("docker", "exec", controller, "mv", temporary, dst)
            created = True
            report["staging"] = ("PASS_UPDATED_EXISTING_PROJECT" if replaced
                                 else "PASS_CREATED_NEW_PROJECT")
        hashes_equal(controller, dst, expected)
        controller_scan(target["controller_scan_url"], token, ssl_context)
        hashes_equal(controller, dst, expected)
        report["controller_scan"] = "HTTP_ACCEPTED_AND_IDLE"
        if replaced:
            report["previous_version_preserved_at"] = previous
        report["status"] = "CONTROLLER_STAGED_AND_SCANNED_NO_EAM"
        print("SELECTED_TEST_CONTROLLER_STAGE_PASS")
        print("EAM_SEND_PROJECT=NOT_RUN")
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        # Only rollback if we actually changed the installed target.
        if created or replaced:
            try:
                if exists(controller, dst):
                    execute("docker", "exec", controller, "mv", dst, rejected)
                if replaced and exists(controller, previous):
                    execute("docker", "exec", controller, "mv", previous, dst)
                    report["rollback"] = "PRIOR_TEST_PROJECT_RESTORED"
                else:
                    report["rollback"] = "NEW_TEST_PROJECT_REMOVED"
                controller_scan(target["controller_scan_url"], token, ssl_context)
            except Exception:
                report["rollback"] = "ENGINEER_REQUIRED"
        raise
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (backup / "evidence.json").write_text(json.dumps(report, indent=2) + "\n",
                                              encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    report = stage(args.factory, args.gateway, args.project, args.sha)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
