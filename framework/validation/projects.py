"""Native Ignition 8.3 project validation facade.

This module intentionally shares reusable_cicd.core.validate_project logic,
so legacy and new workflows cannot silently diverge.
"""
from pathlib import Path
from reusable_cicd.core import validate_project

def validate_native_ignition_project(project_dir: Path, expected_name: str) -> dict:
    return validate_project(project_dir, expected_name)
