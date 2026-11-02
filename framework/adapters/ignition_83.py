"""Native Ignition 8.3 project resource validation adapter."""
from pathlib import Path
from reusable_cicd.core import validate_project

def validate_native_project(path: Path, title: str) -> dict:
    return validate_project(path, title)
