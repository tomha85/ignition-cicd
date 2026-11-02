"""Explicit reviewed target registration; source manifests alone grant no authority."""
import json
from pathlib import Path
from reusable_cicd.core import FrameworkError, load_factory

def check_target_registry(root: Path) -> dict:
    file = root / "targets/lab-targets.json"
    if not file.is_file() or file.is_symlink():
        raise FrameworkError("LAB target registry missing or unsafe")
    data = json.loads(file.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("targets"), list):
        raise FrameworkError("invalid LAB target registry")
    ids = set()
    for target in data["targets"]:
        if not isinstance(target, dict):
            raise FrameworkError("invalid target registry item")
        key = target.get("target_id")
        if not isinstance(key, str) or key in ids:
            raise FrameworkError("invalid or duplicate target id")
        ids.add(key)
        factory_id = target.get("factory_id")
        gateway_id = target.get("gateway_id")
        factory = load_factory(root / "factories", factory_id)
        gateway = next((g for g in factory["gateways"] if g["gateway_id"] == gateway_id), None)
        if gateway is None:
            raise FrameworkError("registered Gateway missing")
        env = gateway["environments"].get("test")
        if env is None or env["target_id"] != key:
            raise FrameworkError("target registry / factory TEST manifest mismatch")
        if target.get("environment") != "test":
            raise FrameworkError("registry can contain LAB TEST only")
        if target.get("eam_send_commissioned") is not False:
            raise FrameworkError("EAM Agent deployment not commissioned in V2")
        if target.get("production_approved") is not False:
            raise FrameworkError("production must be denied")
        if target.get("controller_stage_approved") is True:
            approved = (factory_id, gateway_id, target.get("approved_project"))
            if approved != ("lab-warehouse", "warehouse-main", "FactoryASmoke"):
                raise FrameworkError("unsupported Controller stage target")
    if not ids:
        raise FrameworkError("empty target registry")
    return {"registered_test_targets": len(ids), "eam_send_commissioned": False,
            "production_approved": False, "status": "TARGET_REGISTRY_VALIDATED_NO_EAM_AGENT_RELEASE"}


def require_production_authorization(*_args, **_kwargs):
    raise FrameworkError("HOLD: production deployment has not been qualified or authorized")
