"""Produce an immutable-source TEST plan; planning alone never deploys."""
from pathlib import Path
from reusable_cicd.core import plan_release
from framework.validation.structure import qualify_repository


def plan_test(root: Path, factory: str, gateway: str, project: str, sha: str) -> dict:
    qualify_repository(root)
    plan = plan_release(root / "factories", factory, gateway, "test", sha)
    matches = [p for p in plan["projects"] if p["name"] == project]
    if len(matches) != 1:
        from reusable_cicd.core import FrameworkError
        raise FrameworkError("project not registered on selected TEST Gateway")
    return {"factory_id": factory, "gateway_id": gateway,
            "project": project, "sha": sha,
            "source_hashes": matches[0]["sha256"],
            "status": "VALIDATED_NOT_DEPLOYED",
            "controller_staged": False, "agent_deployed": False,
            "gateway_runtime": "NOT_TESTED", "production_approved": False}


def resolve_project_gateway(root: Path, factory: str, project: str) -> str:
    """Choose the ONLY manifest Gateway for project, never guess on ambiguity."""
    import re
    from reusable_cicd.core import FrameworkError, load_factory

    if not isinstance(project, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_.-]{0,127}", project
    ):
        raise FrameworkError("invalid project name")
    manifest = load_factory(root / "factories", factory)
    matches = [
        gw["gateway_id"] for gw in manifest["gateways"]
        if any(p["name"] == project for p in gw["projects"])
    ]
    if not matches:
        raise FrameworkError("project not registered in selected factory: " + project)
    if len(matches) != 1:
        raise FrameworkError(
            "AMBIGUOUS_GATEWAY: project " + project + " is assigned to multiple Gateways: "
            + ", ".join(sorted(matches))
            + "; engineering must resolve manifest mapping before staging"
        )
    gateway = next(x for x in manifest["gateways"] if x["gateway_id"] == matches[0])
    if "test" not in gateway["environments"]:
        raise FrameworkError("selected Gateway has no TEST environment")
    return matches[0]
