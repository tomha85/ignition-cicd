"""Check factory environment catalogs match the authoritative factory manifests."""
import json
from pathlib import Path
from reusable_cicd.core import FrameworkError, discover_factories, load_factory

ALLOWED = ("dev", "test", "production")


def check_environments(root: Path) -> dict:
    catalog = root / "factories"
    count = 0
    for factory_id in discover_factories(catalog):
        factory = load_factory(catalog, factory_id)
        expected = {env: {} for env in ALLOWED}
        for gateway in factory["gateways"]:
            for env, target in gateway["environments"].items():
                expected[env][gateway["gateway_id"]] = {
                    "target_id": target["target_id"],
                    "github_environment": target["github_environment"],
                }
        for env in ALLOWED:
            path = catalog / factory_id / "environments" / (env + ".json")
            if not path.is_file() or path.is_symlink():
                raise FrameworkError("environment file missing/unsafe: " + str(path))
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("schema_version") != 1 or obj.get("factory_id") != factory_id or obj.get("environment") != env:
                raise FrameworkError("environment identity mismatch: " + str(path))
            if obj.get("gateways") != expected[env]:
                raise FrameworkError("environment targets drift from factory manifest: " + str(path))
            if obj.get("deployment_enabled") is not False:
                raise FrameworkError("environment deployment must remain disabled")
            if env == "production" and obj.get("approval_required") is not True:
                raise FrameworkError("production approval gate missing")
            count += 1
    return {"environment_documents": count, "status": "ENVIRONMENTS_CONSISTENT_DEPLOYMENT_DISABLED"}
