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
