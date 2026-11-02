"""TEST-only EAM orchestrator. Requires commissioned Controller-local bridge and Agents.

Never claims task completion from invocation receipt. Backs up both Gateway project
trees before staging, and verifies target files after the EAM Send Project task.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone

from eam_multi_factory import release_plan

ROOT = Path(__file__).resolve().parents[1]
DATA = "/usr/local/bin/ignition/data"
CTRL = "ignition-eam-controller"
REQUESTS = DATA + "/eam-multi-factory-requests"
REPORT = ROOT / "evidence/eam-multi-factory-deploy.json"
CONTAINERS = {"factory_a": "ignition-factory-a-test",
              "factory_b": "ignition-factory-b-test",
              "factory_c": "ignition-factory-c-test"}

def run(*args, stdout=None):
    return subprocess.run(args, check=True, stdout=stdout, stderr=subprocess.PIPE)

def output(*args):
    return subprocess.check_output(args, text=True).strip()

def inside(container, *args):
    return run("docker", "exec", container, *args)

def present(container, path):
    proc = subprocess.run(["docker", "exec", container, "test", "-e", path],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode not in (0, 1):
        raise RuntimeError("HOLD: cannot inspect authorized Gateway container")
    return proc.returncode == 0

def hashes(container, base, manifest):
    return {rel: output("docker", "exec", container, "sha256sum", base + "/" + rel).split()[0]
            for rel in manifest}

def preflight(factory):
    if os.environ.get("IGNITION_EAM_LAB_ONLY") != "YES":
        raise RuntimeError("HOLD: TEST-only gate")
    if os.environ.get("IGNITION_EAM_BRIDGE_COMMISSIONED") != "YES":
        raise RuntimeError("HOLD: commissioned native EAM bridge not attested")
    if os.environ.get("IGNITION_EAM_CONTROLLER_CONTAINER") != CTRL:
        raise RuntimeError("HOLD: Controller allowlist")
    agent = CONTAINERS[factory]
    if os.environ.get("IGNITION_EAM_AGENT_CONTAINER") != agent:
        raise RuntimeError("HOLD: Agent allowlist")
    for container in (CTRL, agent):
        if output("docker", "inspect", "--format", "{{.State.Health.Status}}", container) != "healthy":
            raise RuntimeError("HOLD: unhealthy gateway " + container)
    root = Path(os.environ.get("IGNITION_BACKUP_DIR", "")).expanduser().resolve()
    if not root.is_dir() or root == ROOT or ROOT in root.parents:
        raise RuntimeError("HOLD: unsafe backup directory")
    return agent, root

def wait_for(controller, path, deadline_seconds):
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if present(controller, path):
            return json.loads(output("docker", "exec", controller, "cat", path))
        time.sleep(3)
    raise RuntimeError("HOLD: EAM task completion receipt timed out")

def deploy(factory, sha):
    plan = release_plan(factory, sha)
    plan["deployment"] = "HOLD"
    REPORT.parent.mkdir(exist_ok=True)
    agent, backup_root = preflight(factory)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
    backup = backup_root / ("eam-" + factory + "-" + stamp)
    backup.mkdir(mode=0o700)
    plan["backup"] = str(backup)
    project = plan["project"]
    src = ROOT / "ignition-project" / project
    staged = DATA + "/.eam-stage-" + stamp
    prior = DATA + "/.eam-prior-" + stamp
    dest = DATA + "/projects/" + project
    request_path = REQUESTS + "/request.json"
    processing_path = REQUESTS + "/request.processing"
    receipt_path = REQUESTS + "/invoked-" + stamp + ".json"
    submitted = False
    try:
        for container in (CTRL, agent):
            tar = backup / (container + "-projects.tar")
            with tar.open("wb") as stream:
                run("docker", "exec", container, "tar", "-cf", "-", "-C", DATA,
                    "projects", stdout=stream)
            run("tar", "-tf", str(tar), stdout=subprocess.DEVNULL)
        plan["backup_verified"] = True
        if any(present(CTRL, p) for p in (staged, prior, request_path, processing_path, receipt_path)):
            raise RuntimeError("HOLD: Controller staging/request conflict")
        inside(CTRL, "mkdir", "-p", REQUESTS)
        # Controller staging outside monitored project directory.
        run("docker", "cp", str(src), CTRL + ":" + staged)
        inside(CTRL, "chown", "-R", "ignition:ignition", staged)
        if hashes(CTRL, staged, plan["file_hashes"]) != plan["file_hashes"]:
            raise RuntimeError("FAIL: staged Controller files differ from release")
        existed = present(CTRL, dest)
        if existed:
            inside(CTRL, "mv", dest, prior)
        inside(CTRL, "mv", staged, dest)
        if hashes(CTRL, dest, plan["file_hashes"]) != plan["file_hashes"]:
            raise RuntimeError("FAIL: Controller project content differs from release")
        plan["staging"] = "HASH_VERIFIED"
        # The native Controller bridge must validate this request against its own
        # factory/task/agent allowlist; a started receipt is not sufficient.
        request = {k: plan[k] for k in ("factory", "project", "target_agent",
                                        "eam_task", "release_sha")}
        request["request_id"] = stamp
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(request, f)
            local = f.name
        try:
            run("docker", "cp", local, CTRL + ":" + REQUESTS + "/request.tmp")
            inside(CTRL, "mv", REQUESTS + "/request.tmp", request_path)
        finally:
            Path(local).unlink(missing_ok=True)
        submitted = True
        receipt = wait_for(CTRL, receipt_path, 240)
        if receipt.get("request_id") != stamp or receipt.get("eam_task") != plan["eam_task"] or receipt.get("task_invoked") is not True:
            raise RuntimeError("FAIL: EAM task invocation receipt missing or reports failure")
        plan["eam_task_status"] = "INVOKED_AGENT_RESULT_PENDING"
        # Independent target verification (not only task invocation).
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if present(agent, dest):
                try:
                    if hashes(agent, dest, plan["file_hashes"]) == plan["file_hashes"]:
                        plan["agent_verification"] = "FILES_MATCH"
                        plan["eam_task_status"] = "AGENT_CONTENT_VERIFIED"
                        plan["deployment"] = "PASS"
                        break
                except subprocess.CalledProcessError:
                    pass
            time.sleep(3)
        if plan["deployment"] != "PASS":
            raise RuntimeError("FAIL: Agent project files do not match approved release")
        plan["e2e_rendered"] = "NOT_TESTED"
    except Exception as exc:
        plan["error"] = str(exc)
        # Never overwrite a Controller after an EAM task might have begun;
        # preserve backups and require reviewed recovery in that case.
        if not submitted and present(CTRL, prior):
            if present(CTRL, dest):
                failed = DATA + "/.eam-failed-" + stamp
                inside(CTRL, "mv", dest, failed)
            inside(CTRL, "mv", prior, dest)
            plan["controller_restore"] = "FILES_RESTORED_SCAN_PENDING"
        raise
    finally:
        REPORT.write_text(json.dumps(plan, indent=2) + "\n")
        (backup / "evidence.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory", required=True, choices=sorted(CONTAINERS))
    p.add_argument("--sha", required=True)
    args = p.parse_args()
    print(json.dumps(deploy(args.factory, args.sha), indent=2))

if __name__ == "__main__":
    main()
