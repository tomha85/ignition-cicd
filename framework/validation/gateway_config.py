"""Validate *curated* Ignition Gateway config metadata without deploying it."""
import json
from pathlib import Path
from reusable_cicd.core import FrameworkError

FORBIDDEN_NAMES = (".env", ".key", ".pem", ".p12", ".pfx", ".gwbk", ".db", ".sqlite")


def inspect_gateway(root: Path, factory: str, gateway: str) -> dict:
    base = root / "factories" / factory / "gateways" / gateway / "config"
    path = base / "gateway.json"
    if not path.is_file() or path.is_symlink() or base.is_symlink():
        raise FrameworkError("Gateway curated config metadata missing or unsafe: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("factory_id") != factory or data.get("gateway_id") != gateway:
        raise FrameworkError("Gateway config identity mismatch: " + str(path))
    if data.get("deployment_enabled") is not False:
        raise FrameworkError("Gateway config deployment must remain disabled")
    resources = data.get("resources")
    if not isinstance(resources, list):
        raise FrameworkError("Gateway resources must be a curated list")
    for resource in resources:
        if not isinstance(resource, str) or "\\" in resource or resource.startswith("/"):
            raise FrameworkError("unsafe Gateway resource")
        if any(p in ("", ".", "..") for p in resource.split("/")):
            raise FrameworkError("Gateway resource traversal")
        file = base / resource
        if not file.resolve().is_relative_to(base.resolve()) or not file.is_file() or file.is_symlink():
            raise FrameworkError("unavailable/unsafe curated Gateway resource: " + resource)
        if any(file.name.lower().endswith(x) for x in FORBIDDEN_NAMES):
            raise FrameworkError("sensitive Gateway resource type forbidden: " + resource)
    return {"factory_id": factory, "gateway_id": gateway,
            "resource_count": len(resources), "deployment_enabled": False,
            "physical_mapping": "NOT_VERIFIED", "config_runtime": "NOT_TESTED"}
