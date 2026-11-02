"""Top-level deterministic repository architecture qualification."""
from pathlib import Path
from reusable_cicd.core import FrameworkError, discover_factories, load_factory, validate_catalog
from framework.validation.source_sync import check_mirrors
from framework.validation.gateway_config import inspect_gateway
from framework.validation.environments import check_environments
from framework.security.policies import check_target_registry


def qualify_repository(root: Path) -> dict:
    root = root.resolve()
    expected = ("factories", "framework", "shared/schemas", "targets",
                "compatibility", "tests", ".github/workflows")
    for item in expected:
        if not (root / item).is_dir():
            raise FrameworkError("missing architecture directory: " + item)
    factories = validate_catalog(root / "factories")
    gateways = []
    for name in factories:
        obj = load_factory(root / "factories", name)
        for gateway in obj["gateways"]:
            gateways.append(inspect_gateway(root, name, gateway["gateway_id"]))
    envs = check_environments(root)
    mirrors = check_mirrors(root)
    registry = check_target_registry(root)
    for schema in ("factory.schema.json", "environment.schema.json",
                   "gateway.schema.json", "target-registry.schema.json"):
        path = root / "shared/schemas" / schema
        if not path.is_file():
            raise FrameworkError("missing JSON schema: " + schema)
        import json
        definition = json.loads(path.read_text(encoding="utf-8"))
        if definition.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise FrameworkError("invalid schema dialect: " + schema)
    return {"status": "STRUCTURE_VALIDATED_DEPLOYMENT_NOT_AUTHORIZED",
            "factories": factories, "gateway_configs": gateways,
            "environments": envs, "legacy_parity": mirrors,
            "target_registry": registry,
            "native_ignition_runtime": "NOT_TESTED",
            "eam_agent_transfer": "NOT_TESTED",
            "production_approved": False}
