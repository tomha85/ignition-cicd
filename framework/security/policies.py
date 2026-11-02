"""Manifest-bound TEST Controller staging policy; no implicit Agent/production release."""
import json
import re
from urllib.parse import urlsplit
from pathlib import Path
from reusable_cicd.core import FrameworkError, load_factory


_CONTAINER_ID = re.compile(r"^[a-z][a-z0-9-]{2,79}$")


def _registry(root: Path) -> list[dict]:
    path = root / "targets/lab-targets.json"
    if not path.is_file() or path.is_symlink():
        raise FrameworkError("LAB target registry missing or unsafe")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise FrameworkError("invalid LAB target registry JSON") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise FrameworkError("invalid LAB registry schema")
    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise FrameworkError("invalid or empty LAB target registry")
    return targets


def check_target_registry(root: Path) -> dict:
    ids = set()
    gateways = set()
    targets = _registry(root)
    approved_count = 0
    for target in targets:
        if not isinstance(target, dict):
            raise FrameworkError("invalid target registry item")
        key = target.get("target_id")
        if not isinstance(key, str) or not key.strip() or key in ids:
            raise FrameworkError("invalid or duplicate target id")
        ids.add(key)
        factory_id = target.get("factory_id")
        gateway_id = target.get("gateway_id")
        factory = load_factory(root / "factories", factory_id)
        gateway = next((g for g in factory["gateways"] if g["gateway_id"] == gateway_id), None)
        if gateway is None:
            raise FrameworkError("registered Gateway missing")
        if (factory_id, gateway_id) in gateways:
            raise FrameworkError("duplicate factory/Gateway target registration")
        gateways.add((factory_id, gateway_id))
        env = gateway["environments"].get("test")
        if env is None or env["target_id"] != key:
            raise FrameworkError("target registry / factory TEST manifest mismatch")
        if target.get("environment") != "test":
            raise FrameworkError("registry can contain LAB TEST only")
        if target.get("eam_send_commissioned") is not False:
            raise FrameworkError("EAM Agent deployment not commissioned")
        if target.get("production_approved") is not False:
            raise FrameworkError("production must be denied")
        approved = target.get("controller_stage_approved")
        if type(approved) is not bool:
            raise FrameworkError("explicit bool controller_stage_approved required")
        if approved:
            approved_count += 1
            if target.get("project_scope") != "all_manifest_projects":
                raise FrameworkError("approved target requires exact manifest project scope")
            for name in ("controller_id", "agent_id"):
                container = target.get(name)
                if not isinstance(container, str) or not _CONTAINER_ID.fullmatch(container):
                    raise FrameworkError("approved LAB target requires valid " + name)
            if target["controller_id"] == target["agent_id"]:
                raise FrameworkError("Controller and Agent must be distinct")
            uri = target.get("controller_scan_url")
            if not isinstance(uri, str):
                raise FrameworkError("approved LAB target requires HTTPS Controller scan endpoint")
            parsed = urlsplit(uri)
            if (parsed.scheme != "https" or parsed.hostname not in ("localhost", "127.0.0.1")
                    or parsed.path != "/data/api/v1/scan/projects"
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.port is None):
                raise FrameworkError("Controller scan endpoint must be isolated loopback HTTPS")
        else:
            if target.get("project_scope") is not None:
                raise FrameworkError("uncommissioned target cannot grant project scope")
    return {"registered_test_targets": len(ids),
            "approved_controller_targets": approved_count,
            "eam_send_commissioned": False,
            "production_approved": False,
            "status": "TARGET_REGISTRY_VALIDATED_NO_EAM_AGENT_RELEASE"}


def resolve_controller_stage_target(root: Path, factory: str, gateway: str,
                                    project: str, *, require_approved: bool = True):
    """Return trusted TEST Controller target or None for source-only factory.

    Authorization is based on the entire reviewed factory+Gateway+TEST target,
    not a single hardcoded project. The requested project must be registered
    on that same Gateway and have its native source validated independently.
    """
    check_target_registry(root)
    manifest = load_factory(root / "factories", factory)
    matches = [gw for gw in manifest["gateways"] if gw["gateway_id"] == gateway]
    if len(matches) != 1:
        raise FrameworkError("unknown selected Gateway")
    if not any(p["name"] == project for p in matches[0]["projects"]):
        raise FrameworkError("project not registered on selected Gateway")
    for target in _registry(root):
        if (target["factory_id"] == factory and
                target["gateway_id"] == gateway and
                target["target_id"] == matches[0]["environments"]["test"]["target_id"]):
            if target["controller_stage_approved"]:
                return target
            if require_approved:
                raise FrameworkError("VALIDATE ONLY: selected Gateway TEST Controller not commissioned")
            return None
    raise FrameworkError("selected Gateway TEST target is not registered")


def require_production_authorization(*_args, **_kwargs):
    raise FrameworkError("HOLD: production deployment has not been qualified or authorized")
