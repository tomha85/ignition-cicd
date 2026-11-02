#!/usr/bin/env python3
"""Read-only Factory A EAM commissioning preflight. NEVER launches an EAM task.

A tested Controller stage is not proof of a configured Send Project task,
a connected EAM Agent, or a successful Perspective runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError
from framework.validation.structure import qualify_repository
from framework.deployment.planner import plan_test

FACTORY = "lab-warehouse"
GATEWAY = "warehouse-main"
PROJECT = "FactoryASmoke"
TARGET = "lab-warehouse-test-agent"
CONTROLLER = "ignition-eam-controller"
AGENT = "ignition-eam-agent"
DATA = "/usr/local/bin/ignition/data"
EVIDENCE = ROOT / "evidence/eam-factory-a-preflight.json"


def docker_result(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], text=True, capture_output=True, timeout=25)


def container_state(container: str) -> dict:
    p = docker_result("inspect", "--format", "{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}", container)
    if p.returncode:
        return {"running": False, "health": "UNAVAILABLE"}
    parts = p.stdout.strip().split()
    return {"running": parts[0] == "true" if parts else False,
            "health": parts[1] if len(parts) > 1 else "UNKNOWN"}


def remote_project_status(container: str, hashes: dict) -> str:
    base = DATA + "/projects/" + PROJECT
    p = docker_result("exec", container, "test", "-d", base)
    if p.returncode == 1:
        return "NOT_PRESENT"
    if p.returncode:
        return "UNAVAILABLE"
    for rel, digest in hashes.items():
        value = docker_result("exec", container, "sha256sum", base + "/" + rel)
        if value.returncode != 0:
            return "MISSING_OR_UNREADABLE"
        if value.stdout.split()[0] != digest:
            return "HASH_MISMATCH"
    return "FILES_MATCH"


def preflight(sha: str, inspect_lab: bool) -> dict:
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise FrameworkError("invalid release SHA")
    qualify_repository(ROOT)
    source = plan_test(ROOT, FACTORY, GATEWAY, PROJECT, sha)
    registry = json.loads((ROOT / "targets/lab-targets.json").read_text(encoding="utf-8"))
    entries = [e for e in registry["targets"] if e["target_id"] == TARGET]
    if len(entries) != 1:
        raise FrameworkError("Factory A target not uniquely registered")
    e = entries[0]
    # Controller staging is scoped to source-verified Gateway projects, not
    # one hardcoded approved_project. Agent commissioning is still a separate HOLD.
    if (e.get("factory_id"), e.get("gateway_id"),
        e.get("controller_id"), e.get("agent_id"), e.get("environment"),
        e.get("project_scope"), e.get("controller_stage_approved")) != (
            FACTORY, GATEWAY, CONTROLLER, AGENT, "test",
            "all_manifest_projects", True):
        raise FrameworkError("target identity is not approved for TEST")
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "release_sha": sha,
        "factory": FACTORY, "gateway": GATEWAY, "project": PROJECT,
        "target_id": TARGET,
        "mode": "READ_ONLY_EAM_COMMISSIONING_PREFLIGHT",
        "status": "HOLD",
        "controller_staging": "ALREADY_TESTED_IN_PRIOR_RUN_NOT_REEXECUTED",
        "eam_send_project": "NOT_RUN",
        "agent_project_deployed": "NOT_VERIFIED",
        "perspective_browser": "NOT_TESTED",
        "production_approved": False,
        "blockers": [],
        "registered_eam_task": "NOT_ATTESTED",
    }
    if e.get("eam_send_commissioned") is not True:
        result["blockers"].append("EAM_SEND_NOT_COMMISSIONED_IN_TARGET_REGISTRY")
    if os.environ.get("IGNITION_EAM_BRIDGE_COMMISSIONED") != "YES":
        result["blockers"].append("EAM_CONTROLLER_BRIDGE_NOT_ATTESTED")
    if os.environ.get("IGNITION_FACTORY_A_SMOKE_TASK_COMMISSIONED") != "YES":
        result["blockers"].append("FACTORY_A_SMOKE_SEND_PROJECT_TASK_NOT_ATTESTED")
    if not inspect_lab:
        result["lab_inspection"] = "NOT_RUN_STATIC_ONLY"
        return result
    if os.environ.get("GITHUB_REPOSITORY") != "tomha85/ignition-cicd":
        raise FrameworkError("incorrect GitHub repository")
    if os.environ.get("GITHUB_REF") != "refs/heads/feat/reusable-multifactory-framework-v1":
        raise FrameworkError("unapproved GitHub ref")
    if os.environ.get("GITHUB_SHA") != sha:
        raise FrameworkError("Git SHA mismatch")
    containers = {}
    for name in (CONTROLLER, AGENT):
        state = container_state(name)
        containers[name] = state
        if not state["running"]:
            result["blockers"].append("LAB_GATEWAY_NOT_RUNNING_" + name)
        if state["health"] != "healthy":
            result["blockers"].append("LAB_GATEWAY_HEALTH_NOT_CONFIRMED_" + name)
    result["containers"] = containers
    if all(s["running"] for s in containers.values()):
        controller_files = remote_project_status(CONTROLLER, source["source_hashes"])
        agent_files = remote_project_status(AGENT, source["source_hashes"])
        result["controller_files"] = controller_files
        result["agent_files"] = agent_files
        if controller_files != "FILES_MATCH":
            result["blockers"].append("CONTROLLER_NATIVE_SOURCE_NOT_VERIFIED")
        if agent_files == "HASH_MISMATCH":
            result["blockers"].append("AGENT_EXISTING_PROJECT_DIFFERS_DO_NOT_OVERWRITE")
        # Agent FILES_MATCH would NOT prove EAM was used or Browser rendered.
    else:
        result["controller_files"] = "NOT_CHECKED"
        result["agent_files"] = "NOT_CHECKED"
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sha", required=True)
    p.add_argument("--inspect-lab", action="store_true")
    args = p.parse_args()
    report = {
        "status": "HOLD", "mode": "READ_ONLY_EAM_COMMISSIONING_PREFLIGHT",
        "eam_send_project": "NOT_RUN", "perspective_browser": "NOT_TESTED",
    }
    try:
        report = preflight(args.sha, args.inspect_lab)
    except Exception as exc:
        report["blockers"] = ["PREFLIGHT_EXCEPTION"]
        report["error"] = str(exc)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    # An uncommissioned LAB MUST NOT produce a green deployment job.
    if report.get("blockers"):
        print("EAM_E2E_DEPLOYMENT=HOLD")
        return 2
    print("EAM_PREFLIGHT_READY_BUT_NO_DEPLOYMENT_PERFORMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
