"""Portable, read-only organization/site/workshop/controller EAM configuration.

The control-plane configuration is deliberately NOT a deployment authorization.
It supports customer-owned EAM Controllers on-prem or in private cloud networks.
No secrets, Gateway connections, PLC writes, task execution or network traffic.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from reusable_cicd.core import FrameworkError

ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
GATEWAY_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
PROJECT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
AGENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
SECRET_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,100}\Z")
HOSTING = {"on_prem", "private_cloud"}
TRANSPORT = {"site_lan", "private_vpn", "private_wan", "private_overlay"}
TOP_KEYS = {"schema_version", "customer_id", "mode", "controllers", "sites", "targets"}
CONTROLLER_KEYS = {
    "controller_id", "hosting", "controller_url", "network",
    "api_token_secret", "ca_file_variable",
}
SITE_KEYS = {"site_id", "display_name", "workshops"}
TARGET_KEYS = {
    "site_id", "workshop_id", "factory_id", "gateway_id", "project",
    "controller_id", "agent_name", "eam_task_name",
}


def require(condition, message):
    if not condition:
        raise FrameworkError("CUSTOMER_TOPOLOGY_HOLD: " + message)


def valid_id(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def url_is_secure(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False
    # Explicit HTTPS+port, no userinfo/URL path: operational reachability and
    # certificate trust MUST be independently verified during commissioning.
    return bool(
        parts.scheme == "https" and parts.hostname and port and
        not parts.username and not parts.password and
        not parts.path.strip("/") and not parts.query and not parts.fragment
    )


def validate_topology(profile):
    require(isinstance(profile, dict) and set(profile) == TOP_KEYS,
            "unsupported topology structure")
    require(type(profile["schema_version"]) is int and profile["schema_version"] == 2,
            "schema_version must be 2")
    require(valid_id(profile["customer_id"]), "invalid customer_id")
    require(profile["mode"] == "plan_only",
            "only plan_only allowed; runtime deployment is NOT authorized")
    controllers = profile["controllers"]
    sites = profile["sites"]
    targets = profile["targets"]
    require(isinstance(controllers, list) and 0 < len(controllers) <= 100,
            "controllers must contain 1..100 entries")
    require(isinstance(sites, list) and 0 < len(sites) <= 200,
            "sites must contain 1..200 entries")
    require(isinstance(targets, list) and 0 < len(targets) <= 500,
            "targets must contain 1..500 entries")

    controller_by_id = {}
    for item in controllers:
        require(isinstance(item, dict) and set(item) == CONTROLLER_KEYS,
                "unexpected Controller fields (never embed credentials)")
        cid = item["controller_id"]
        require(valid_id(cid) and cid not in controller_by_id,
                "duplicate or invalid controller_id")
        require(item["hosting"] in HOSTING,
                "Controller hosting must be on_prem or private_cloud")
        require(item["network"] in TRANSPORT,
                "Controller network must be a trusted private transport")
        require(url_is_secure(item["controller_url"]),
                "Controller URL must be HTTPS base with explicit port")
        for key in ("api_token_secret", "ca_file_variable"):
            require(isinstance(item[key], str) and
                    bool(SECRET_NAME.fullmatch(item[key])),
                    key + " must be a secret/variable NAME, never the secret value")
        controller_by_id[cid] = item

    site_by_id = {}
    for item in sites:
        require(isinstance(item, dict) and set(item) == SITE_KEYS,
                "unexpected Site fields")
        sid = item["site_id"]
        require(valid_id(sid) and sid not in site_by_id,
                "duplicate or invalid site_id")
        label = item["display_name"]
        require(isinstance(label, str) and 0 < len(label) <= 80 and
                label == label.strip() and "\n" not in label,
                "invalid Site display_name")
        workshops = item["workshops"]
        require(isinstance(workshops, list) and
                0 < len(workshops) <= 100 and
                all(valid_id(x) for x in workshops) and
                len(set(workshops)) == len(workshops),
                "invalid/duplicate workshops for Site")
        site_by_id[sid] = set(workshops)

    site_targets = set()
    gateway_targets = set()
    task_targets = set()
    for item in targets:
        require(isinstance(item, dict) and set(item) == TARGET_KEYS,
                "unexpected target fields")
        require(item["site_id"] in site_by_id, "target references unknown Site")
        require(item["workshop_id"] in site_by_id[item["site_id"]],
                "target references unregistered workshop")
        require(item["controller_id"] in controller_by_id,
                "target references unknown EAM Controller")
        for key in ("factory_id", "gateway_id"):
            require(valid_id(item[key]), "invalid " + key)
        require(isinstance(item["project"], str) and
                bool(PROJECT.fullmatch(item["project"])), "invalid project")
        for key in ("agent_name", "eam_task_name"):
            require(isinstance(item[key], str) and
                    bool(AGENT.fullmatch(item[key])),
                    "invalid/unsafe " + key)
        physical_target = (item["factory_id"], item["gateway_id"], item["project"])
        logical_target = (item["site_id"], item["workshop_id"],
                          item["controller_id"], item["agent_name"], item["project"])
        task_target = (item["controller_id"], item["eam_task_name"])
        require(physical_target not in gateway_targets,
                "same factory/Gateway/project mapped twice")
        require(logical_target not in site_targets,
                "duplicate Site/Workshop/Agent/Project")
        require(task_target not in task_targets,
                "EAM task reused for another target: unsafe ambiguous binding")
        gateway_targets.add(physical_target)
        site_targets.add(logical_target)
        task_targets.add(task_target)
    return profile


def flatten(profile):
    """Convert v2 topology to the existing v1 plan interface, no deployment."""
    validate_topology(profile)
    controllers = {c["controller_id"]: c for c in profile["controllers"]}
    targets = []
    for t in profile["targets"]:
        c = controllers[t["controller_id"]]
        targets.append({
            "factory_id": t["factory_id"],
            "gateway_id": t["gateway_id"],
            "project": t["project"],
            "eam": {
                "controller_url": c["controller_url"],
                "agent_name": t["agent_name"],
                "network": c["network"],
                "api_token_secret": c["api_token_secret"],
                "ca_file_variable": c["ca_file_variable"],
            },
        })
    return {"schema_version": 1, "customer_id": profile["customer_id"],
            "mode": "plan_only", "targets": targets}


def annotate(plan, profile):
    """Add logical/site identity and hosting without exposing endpoints/secrets."""
    targets = {(t["factory_id"], t["gateway_id"], t["project"]): t
               for t in profile["targets"]}
    controllers = {c["controller_id"]: c for c in profile["controllers"]}
    for item in plan["targets"]:
        key = (item["factory_id"], item["gateway_id"], item["project"])
        t = targets[key]
        c = controllers[t["controller_id"]]
        item.update({
            "site_id": t["site_id"],
            "workshop_id": t["workshop_id"],
            "controller_id": t["controller_id"],
            "controller_hosting": c["hosting"],
            "eam_task_name": t["eam_task_name"],
            "network_access": "NOT_VERIFIED",
            "eam_task_binding": "NOT_VERIFIED",
        })
    plan["schema_version"] = 2
    plan["site_count"] = len({t["site_id"] for t in plan["targets"]})
    plan["workshop_count"] = len(
        {(t["site_id"], t["workshop_id"]) for t in plan["targets"]})
    plan["controller_count"] = len({t["controller_id"] for t in plan["targets"]})
    plan["deployment_authorized"] = False
    return plan
