"""Public V3 manifest API; delegates to existing, regression-tested canonical engine.

Do not duplicate validators: reusable_cicd.core is source of truth during migration.
"""
from pathlib import Path
from reusable_cicd.core import (
    FrameworkError, discover_factories, load_factory, plan_release, validate_catalog
)

def validate_factory_manifest(root: Path, factory_id: str) -> dict:
    """Validate an existing factory ID. No gateway/device side effects."""
    catalog = root / "factories"
    validate_catalog(catalog)
    return load_factory(catalog, factory_id)

def selected_test_plan(root: Path, factory_id: str, gateway_id: str,
                       sha: str) -> dict:
    """Deterministic source plan; no deployment authority is granted."""
    validate_catalog(root / "factories")
    return plan_release(root / "factories", factory_id, gateway_id, "test", sha)
