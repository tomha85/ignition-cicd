"""Approved local LAB target descriptors only; never infer OT destinations."""
from pathlib import Path
from framework.security.policies import check_target_registry

def describe_lab_targets(root: Path) -> dict:
    return check_target_registry(root)
