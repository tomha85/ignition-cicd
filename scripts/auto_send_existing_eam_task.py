#!/usr/bin/env python3
"""Approved LAB TEST only: invoke an existing, verified EAM Send Project task.

Runs after the reviewed Controller stage, never changes EAM task definitions.
No production privileges; Agent resources must be independently verified.
"""
import argparse
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework.security.policies import resolve_controller_stage_target
from scripts.verify_stage_approval import verify as verify_approval

DATA = "/usr/local/bin/ignition/data"
REPORT = ROOT / "evidence/selected-agent-eam.json"
TASK_FIND = "/data/api/v1/resources/find/com.inductiveautomation.eam/eam-tasks/"
TASK_FORCE = "/data/eam/api/v1/eam-tasks/force/"
AGENTS = "/data/eam/api/v1/agents"
FILE_TO_VERIFY = (
    "com.inductiveautomation.perspective/views/Main/view.json",
    "com.inductiveautomation.perspective/page-config/config.json",
)

def require(condition, reason):
    if not condition:
        raise RuntimeError("HOLD: " + reason)

def docker_output(container, *args):
    return subprocess.check_output(
        ["docker", "exec", container, *args], text=True, stderr=subprocess.PIPE,
        timeout=30).strip()

def api(base_url, token, ctx, path, method="GET"):
    request = Request(
        base_url + path, method=method,
        data=b"" if method == "POST" else None,
        headers={"X-Ignition-API-Token": token, "Accept": "application/json"})
    with urlopen(request, context=ctx, timeout=30) as result:
        require(200 <= result.status < 300, "EAM API request rejected")
        raw = result.read()
        return json.loads(raw) if raw else {"http_status": result.status}

def agent_id_matches(data, name, identifier):
    matches = []
    def walk(value):
        if isinstance(value, dict):
            if value.get("name") == name:
                matches.append(value)
            for val in value.values():
                if isinstance(val, (dict, list)):
                    walk(val)
        elif isinstance(value, list):
            for val in value:
                walk(val)
    walk(data)
    return len(matches) == 1 and (
        identifier == name or
        any(val == identifier for val in matches[0].values() if isinstance(val, str)))

def eligible_task(root, factory, gateway, project):
    """Resolve only task bindings explicitly reviewed in target registry."""
    target = resolve_controller_stage_target(root, factory, gateway, project)
    if target.get("eam_send_commissioned") is not True:
        return target, None
    tasks = target.get("eam_tasks", [])
    matches = [t for t in tasks if t.get("project") == project]
    require(len(matches) == 1, "unique, reviewed EAM task binding required")
    task = matches[0]
    require(task.get("task_name") and task.get("agent_name") and
            re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", task["task_name"]),
            "invalid EAM task mapping")
    return target, task

def verify_agent(container, project, expected_description, controller, deadline_seconds=150):
    base = DATA + "/projects/" + project
    desc = DATA + "/projects/" + project + "/project.json"
    end = time.monotonic() + deadline_seconds
    while time.monotonic() < end:
        try:
            agent_json = json.loads(docker_output(container, "cat", desc))
            if agent_json.get("description") != expected_description:
                time.sleep(3)
                continue
            for rel in FILE_TO_VERIFY:
                a = docker_output(container, "sha256sum", base + "/" + rel).split()[0]
                c = docker_output(controller, "sha256sum", base + "/" + rel).split()[0]
                if a != c:
                    break
            else:
                return "AGENT_DESCRIPTION_AND_PERSPECTIVE_FILES_MATCH"
        except (subprocess.CalledProcessError, ValueError, IndexError):
            pass
        time.sleep(3)
    raise RuntimeError("HOLD: EAM Agent content not verified against staged Controller")

def deploy(factory, gateway, project, sha, run_id):
    report = dict(factory=factory, gateway=gateway, project=project, sha=sha,
                  github_run_id=run_id, status="HOLD",
                  eam_send_project="NOT_RUN", agent_verification="NOT_RUN",
                  perspective_browser="NOT_TESTED", production="FORBIDDEN")
    try:
        require(os.getenv("GITHUB_REPOSITORY") == "tomha85/ignition-cicd" and
                os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch",
                "only reviewed TEST dispatch permitted")
        if os.getenv("GITHUB_REF") != "refs/heads/main":
            from scripts.authorize_generic_eam_candidate import require_lab_candidate
            require_lab_candidate(ROOT, factory, gateway, project)
        require(os.getenv("GITHUB_SHA") == sha and re.fullmatch(r"[0-9a-f]{40}", sha),
                "Git release identity mismatch")
        require(os.getenv("GITHUB_RUN_ID") == run_id and
                re.fullmatch(r"[0-9]{1,20}", run_id), "GitHub run identity mismatch")
        target, binding = eligible_task(ROOT, factory, gateway, project)
        if binding is None:
            report["status"] = "EAM_NOT_COMMISSIONED_STAGE_ONLY"
            return report
        require(os.getenv("IGNITION_EAM_AUTO_SEND_ENABLED") == "YES",
                "EAM auto-send environment authorization missing")
        require(os.getenv("IGNITION_TEST_STAGE_CONFIRM") == "ISOLATED_TEST_ONLY",
                "TEST-only gate missing")
        require(os.getenv("IGNITION_CONTROLLER_CONTAINER") == target["controller_id"] and
                os.getenv("IGNITION_AGENT_CONTAINER") == target["agent_id"],
                "Gateway identity mismatch")
        verify_approval(os.environ, os.getenv("GH_APPROVAL_READ_TOKEN"))
        evidence = json.loads((ROOT / "evidence/selected-controller-stage.json").read_text())
        require(evidence.get("sha") == sha and evidence.get("project") == project and
                evidence.get("factory_id") == factory and evidence.get("gateway_id") == gateway and
                evidence.get("backup_verified") is True and
                evidence.get("status") == "CONTROLLER_STAGED_AND_SCANNED_NO_EAM" and
                evidence.get("controller_scan") == "HTTP_ACCEPTED_AND_IDLE" and
                evidence.get("description_stamp", {}).get("github_run_id") == run_id,
                "current run Controller stage and backup evidence required")
        token = os.getenv("IGNITION_CONTROLLER_API_TOKEN")
        ca = Path(os.getenv("IGNITION_CONTROLLER_CA_FILE", "/missing"))
        require(token and ca.is_file() and not ca.is_symlink(), "TLS credentials missing")
        ctx = ssl.create_default_context(cafile=str(ca))
        from urllib.parse import urlsplit
        endpoint = target["controller_scan_url"]
        parts = urlsplit(endpoint)
        base_url = f"{parts.scheme}://{parts.netloc}"
        task = api(base_url, token, ctx, TASK_FIND + quote(binding["task_name"], safe=""))
        require(isinstance(task, dict), "EAM task definition not found")
        config = task.get("config", {})
        settings = config.get("settings", {})
        profile = config.get("profile", {})
        targets = settings.get("targetGateways")
        require(profile.get("type") == "eam_sendProject" and
                settings.get("sourceProject") == project and
                settings.get("selectedGateway") == "__local__" and
                isinstance(targets, list) and len(targets) == 1 and
                not settings.get("targetGroups") and
                profile.get("isSuspended") is False,
                "EAM task configuration or target is not approved")
        owner = (task.get("healthchecks", {}).get("scheduledTaskState", {})
                 .get("result", {}).get("details", {}).get("owner"))
        require(owner == "eam", "unverified EAM task owner")
        agents = api(base_url, token, ctx, AGENTS)
        require(agent_id_matches(agents, binding["agent_name"], targets[0]),
                "EAM task is not bound to expected Agent")
        controller = target["controller_id"]
        agent = target["agent_id"]
        stage_desc = json.loads(docker_output(
            controller, "cat", DATA + "/projects/" + project + "/project.json")
        ).get("description", "")
        require("EAM TEST STAGED" in stage_desc and sha[:12] in stage_desc and
                "run=" + run_id in stage_desc and "NOT AGENT VERIFIED" in stage_desc,
                "expected version stamp missing from Controller")
        report["eam_task"] = binding["task_name"]
        # The existing EAM task is invoked once. Never auto-retry on timeout.
        api(base_url, token, ctx, TASK_FORCE +
            quote(owner, safe="") + "/" + quote(binding["task_name"], safe=""),
            method="POST")
        report["eam_send_project"] = "TASK_INVOCATION_ACCEPTED"
        report["agent_verification"] = verify_agent(
            agent, project, stage_desc, controller)
        report["status"] = "AGENT_RESOURCES_VERIFIED_NOT_BROWSER_TESTED"
        return report
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["status"] = "HOLD"
        raise
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    for key in ("factory", "gateway", "project", "sha", "run-id"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    try:
        report = deploy(args.factory, args.gateway, args.project, args.sha, args.run_id)
        print(json.dumps(report, indent=2))
    except Exception as exc:
        print("AUTO_EAM_HOLD: " + type(exc).__name__, file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
