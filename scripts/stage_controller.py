"""Fail-closed TEST-only Docker Controller staging.

No EAM trigger is issued. A human must verify Gateway scan/runtime first.
Only allowlisted Docker containers and one allowlisted project are permitted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "ignition-test.json"
DESTROOT = "/usr/local/bin/ignition/data/projects"
PROJECT = "DeploymentSmokeTest"
CONTROLLER = "ignition-eam-controller"
AGENT = "ignition-eam-agent"

def check_config():
    d = json.loads(MANIFEST.read_text())
    expected = {
        "environment": "ignition-test",
        "project": PROJECT,
        "source_path": "ignition-project/DeploymentSmokeTest",
        "controller_container": CONTROLLER,
        "agent_container": AGENT,
        "production_approved": False,
        "automatic_eam_enabled": False,
    }
    for key, value in expected.items():
        if d.get(key) != value:
            raise RuntimeError("Manifest gate failed: " + key)
    if not d.get("requires_gateway_scan") or not d.get("requires_runtime_smoke"):
        raise RuntimeError("Cannot bypass runtime verification")
    src = ROOT / d["source_path"]
    if not src.is_dir() or not (src / "project.json").is_file():
        raise RuntimeError("Missing source project")
    for f in src.rglob("*"):
        if f.is_symlink():
            raise RuntimeError("Symlink not allowed: " + str(f))
    return src

def run(*args, stdout=None):
    return subprocess.run(args, stdout=stdout, stderr=subprocess.PIPE, check=True)

def inspect(name):
    v = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Running}}", name], text=True).strip()
    if v != "true":
        raise RuntimeError("Docker container not running: " + name)

def stage():
    if os.getenv("IGNITION_LAB_ONLY") != "YES":
        raise RuntimeError("TEST ONLY gate")
    if os.getenv("IGNITION_CONTROLLER_CONTAINER") != CONTROLLER:
        raise RuntimeError("Unexpected Controller target")
    if os.getenv("IGNITION_AGENT_CONTAINER") != AGENT:
        raise RuntimeError("Unexpected Agent target")
    sha = os.getenv("RELEASE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid release sha")
    src = check_config()
    inspect(CONTROLLER)
    inspect(AGENT)
    backup_root = os.getenv("IGNITION_BACKUP_DIR", "")
    if not backup_root:
        raise RuntimeError("IGNITION_BACKUP_DIR missing")
    backup_base = Path(backup_root).expanduser().resolve()
    if not backup_base.is_dir() or not backup_base.is_absolute():
        raise RuntimeError("Backup directory must exist")
    if backup_base == ROOT or ROOT in backup_base.parents:
        raise RuntimeError("Backup cannot be placed in checkout")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_base / (stamp + "-" + sha[:12])
    backup.mkdir(mode=0o700, exist_ok=False)
    dst = DESTROOT + "/" + PROJECT
    # Take Controller filesystem backup before any mutation; separate .gwbk recommended.
    with (backup / "controller-projects.tar").open("wb") as f:
        run("docker", "exec", CONTROLLER, "tar", "-cf", "-", "-C",
            "/usr/local/bin/ignition/data", "projects", stdout=f)
    if (backup / "controller-projects.tar").stat().st_size == 0:
        raise RuntimeError("Backup empty")
    run("tar", "-tf", str(backup / "controller-projects.tar"))
    # Lab is CREATE-ONLY; never overwrite existing project automatically.
    p = subprocess.run(["docker", "exec", CONTROLLER, "test", "-e", dst])
    if p.returncode == 0:
        raise RuntimeError("PROJECT_ALREADY_EXISTS: no overwrite. Use reviewed update procedure.")
    if p.returncode != 1:
        raise RuntimeError("Could not inspect destination")
    # Project files only; do not copy directly to Agent.
    run("docker", "cp", str(src), CONTROLLER + ":" + dst)
    run("docker", "exec", "-u", "0", CONTROLLER, "chown", "-R", "ignition:ignition", dst)
    source_hashes = {f.relative_to(src).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                     for f in src.rglob("*") if f.is_file()}
    for rel, h in source_hashes.items():
        received = subprocess.check_output(["docker", "exec", CONTROLLER,
            "sha256sum", dst + "/" + rel], text=True).split()[0]
        if received != h:
            raise RuntimeError("Stage content mismatch: " + rel)
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    report = {
        "sha": sha, "project": PROJECT, "controller": CONTROLLER,
        "result": "STAGED_FILES_ONLY",
        "backup": str(backup),
        "files_verified": len(source_hashes),
        "gateway_scan": "NOT_RUN",
        "controller_runtime": "NOT_VERIFIED",
        "eam_send_project": "NOT_RUN",
        "agent_runtime": "NOT_VERIFIED",
        "e2e": "HOLD",
    }
    (evidence / "controller-stage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    if args.check_config == args.stage:
        parser.error("Select exactly one of --check-config / --stage")
    if args.check_config:
        print("MANIFEST_AND_SOURCE_PASS", check_config())
    else:
        stage()
