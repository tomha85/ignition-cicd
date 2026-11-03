"""Generic, configuration-driven EAM deployment planner (READ-ONLY candidate).

Never accesses a Gateway, Docker daemon, GitHub API, or executes tasks.
Commissioning is separately authorized by an independent deployment engine.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from framework.deployment.planner import resolve_project_gateway
from reusable_cicd.core import FrameworkError, load_factory

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_RUNNER = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_TASK = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")

def hold(message: str):
    raise FrameworkError("HOLD: " + message)

def _read_json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        hold("missing or symlinked configuration")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        hold("invalid configuration JSON")
    if not isinstance(value, dict):
        hold("expected configuration object")
    return value

def resolve(root: Path, factory: str, project: str,
            environment: str = "test", gateway: str | None = None) -> dict:
    """Resolve only unambiguous, explicitly registered TEST Gateway/Agent/task."""
    if environment != "test":
        hold("generic engine is TEST-only; production is forbidden")
    if not all(isinstance(v, str) and _ID.fullmatch(v)
               for v in (factory, project)):
        hold("invalid factory or project identifier")
    manifest = load_factory(root / "factories", factory)
    resolved_gateway = resolve_project_gateway(root, factory, project)
    if gateway is not None and gateway != resolved_gateway:
        hold("explicit gateway does not match verified factory mapping")
    gateway = resolved_gateway
    selected = next(x for x in manifest["gateways"] if x["gateway_id"] == gateway)
    target_id = selected["environments"]["test"]["target_id"]

    config = _read_json(root / "generic-eam" / "targets.json")
    if config.get("schema_version") != 1 or not isinstance(config.get("targets"), list):
        hold("invalid generic target catalog")
    targets = config["targets"]
    ids = [t.get("target_id") for t in targets if isinstance(t, dict)]
    if len(ids) != len(set(ids)) or any(not isinstance(v, str) for v in ids):
        hold("duplicate or invalid target IDs")
    matches = [t for t in targets if isinstance(t, dict) and
               t.get("target_id") == target_id and
               t.get("factory_id") == factory and
               t.get("gateway_id") == gateway and
               t.get("environment") == "test"]
    if len(matches) != 1:
        hold("target not uniquely mapped to factory/gateway/environment")
    target = matches[0]
    allowed_keys = {"target_id", "factory_id", "gateway_id", "environment",
                    "runner_labels", "controller", "agent", "tasks",
                    "deployment_enabled", "approval_environment"}
    if set(target) != allowed_keys:
        hold("unknown or missing target fields")
    if type(target["deployment_enabled"]) is not bool:
        hold("deployment_enabled must be boolean")
    if target["deployment_enabled"]:
        hold("generic candidate cannot authorize deployment")
    labels = target["runner_labels"]
    if not isinstance(labels, list) or not labels or len(set(labels)) != len(labels) or any(
            not isinstance(label, str) or not _RUNNER.fullmatch(label) for label in labels):
        hold("invalid runner labels")
    if "self-hosted" not in labels:
        hold("non-self-hosted OT runner forbidden")
    controller, agent = target["controller"], target["agent"]
    if not isinstance(controller, dict) or not isinstance(agent, dict):
        hold("invalid endpoint config")
    if set(controller) != {"id", "api_base_url", "secret_ref", "ca_ref"} or set(agent) != {"id", "eam_agent_name"}:
        hold("unexpected Controller/Agent fields")
    for value in (controller["id"], agent["id"], agent["eam_agent_name"]):
        if not isinstance(value, str) or not _ID.fullmatch(value):
            hold("invalid Controller or Agent identity")
    if controller["id"] == agent["id"]:
        hold("Controller and Agent identities must differ")
    url = urlsplit(controller["api_base_url"])
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/") or
            not (url.port and 1 <= url.port <= 65535)):
        hold("Controller API must be HTTPS endpoint without inline credentials")
    for key in ("secret_ref", "ca_ref"):
        ref = controller[key]
        if not isinstance(ref, str) or not re.fullmatch(r"^[A-Z][A-Z0-9_]{2,100}$", ref):
            hold("invalid environment secret/CA reference")
    if not isinstance(target["approval_environment"], str) or not target["approval_environment"].startswith("ignition-test"):
        hold("TEST approval environment required")
    tasks = target["tasks"]
    if not isinstance(tasks, list):
        hold("invalid EAM task list")
    names, projects = set(), set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {"project", "task_name", "agent_name"}:
            hold("invalid task fields")
        p, name, dest = task["project"], task["task_name"], task["agent_name"]
        if (not isinstance(p, str) or not _ID.fullmatch(p) or p in projects
                or not isinstance(name, str) or not _TASK.fullmatch(name)
                or name in names or dest != agent["eam_agent_name"]
                or p not in {x["name"] for x in selected["projects"]}):
            hold("unverified, ambiguous or cross-target EAM task")
        projects.add(p); names.add(name)
    selected_tasks = [t for t in tasks if t["project"] == project]
    if len(selected_tasks) != 1:
        hold("selected project has no unique reviewed EAM task")
    task = selected_tasks[0]
    return {
        "status": "CONFIG_RESOLVED_NOT_DEPLOYED",
        "factory_id": factory, "gateway_id": gateway,
        "project": project, "target_id": target_id,
        "environment": "test", "runner_labels": labels,
        "github_environment": target["approval_environment"],
        "controller_id": controller["id"],
        "controller_api_base_url": controller["api_base_url"],
        "api_token_secret_ref": controller["secret_ref"],
        "trusted_ca_ref": controller["ca_ref"],
        "agent_id": agent["id"],
        "agent_name": agent["eam_agent_name"],
        "eam_task": task["task_name"],
        "deployment_authorized": False,
        "agent_verification": "NOT_RUN",
        "production_approved": False,
    }
