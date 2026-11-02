"""Factory FAT requirements: missing real signal evidence must never become PASS."""
import json
from pathlib import Path
from reusable_cicd.core import FrameworkError, discover_factories


def check_requirements(root: Path) -> dict:
    validated = []
    for factory in discover_factories(root / "factories"):
        file = root / "factories" / factory / "tests/requirements.json"
        if not file.is_file() or file.is_symlink():
            raise FrameworkError("FAT requirements file missing or unsafe: " + str(file))
        document = json.loads(file.read_text(encoding="utf-8"))
        if document.get("schema_version") != 1 or document.get("factory_id") != factory:
            raise FrameworkError("invalid FAT requirements identity")
        if document.get("fat_status") != "NOT_TESTED":
            raise FrameworkError("FAT cannot claim PASS without independent live evidence")
        reqs = document.get("requirements")
        if not isinstance(reqs, list):
            raise FrameworkError("FAT requirements must be a list")
        seen = set()
        for req in reqs:
            if not isinstance(req, dict) or not isinstance(req.get("id"), str):
                raise FrameworkError("invalid FAT requirement")
            if req["id"] in seen or not req["id"].strip():
                raise FrameworkError("duplicate/empty FAT requirement id")
            seen.add(req["id"])
            if req.get("status") != "NOT_TESTED":
                raise FrameworkError("FAT requirement must remain NOT_TESTED in this LAB candidate")
            if not isinstance(req.get("source_reference"), str) or not req["source_reference"].strip():
                raise FrameworkError("FAT requirement must have source provenance")
        validated.append({"factory_id": factory, "requirement_count": len(reqs),
                          "fat_status": "NOT_TESTED"})
    return {"factory_requirements": validated, "status": "REQUIREMENTS_DOCUMENTED_FAT_NOT_TESTED"}
