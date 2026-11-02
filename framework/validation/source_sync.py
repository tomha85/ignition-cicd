"""Prevent silent source drift during migration to factory-owned native projects."""
import hashlib
import json
from pathlib import Path

from reusable_cicd.core import FrameworkError


def compare_native_project_trees(root: Path, project_src: str, legacy_src: str) -> int:
    """Require exact byte-for-byte parity of two explicit compatibility mirrors."""
    root = root.resolve()
    paths = []
    for label, value in (("factory", project_src), ("legacy", legacy_src)):
        if not isinstance(value, str) or value.startswith("/") or "\\" in value:
            raise FrameworkError("unsafe source mirror: " + str(value))
        if any(x in ("", ".", "..") for x in value.split("/")):
            raise FrameworkError("unsafe source mirror traversal: " + value)
        path = root / value
        if not path.resolve().is_relative_to(root) or not path.is_dir() or path.is_symlink():
            raise FrameworkError(label + " mirror outside checkout or missing: " + value)
        paths.append(path)
    def collect(base):
        result = {}
        for f in sorted(base.rglob("*")):
            if f.is_symlink():
                raise FrameworkError("symlink forbidden in native mirror: " + str(f))
            if f.is_file():
                result[f.relative_to(base).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
        return result
    a, b = map(collect, paths)
    if not a or a != b:
        raise FrameworkError("legacy/native project drift: " + project_src + " vs " + legacy_src)
    return len(a)


def check_mirrors(root: Path) -> dict:
    path = root / "compatibility/legacy-source-mirrors.json"
    if not path.is_file() or path.is_symlink():
        raise FrameworkError("missing legacy compatibility mirror registry")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("mirrors"), list):
        raise FrameworkError("invalid source mirror registry")
    seen = set()
    total = 0
    for pair in data["mirrors"]:
        if not isinstance(pair, dict):
            raise FrameworkError("invalid mirror record")
        canonical = pair.get("canonical")
        legacy = pair.get("legacy")
        if not isinstance(canonical, str) or not canonical.startswith("factories/"):
            raise FrameworkError("canonical project must be factory-owned")
        if not isinstance(legacy, str) or not legacy.startswith("ignition-project/"):
            raise FrameworkError("legacy path must be under ignition-project")
        if (canonical, legacy) in seen:
            raise FrameworkError("duplicate source mirror")
        seen.add((canonical, legacy))
        total += compare_native_project_trees(root, canonical, legacy)
    if not seen:
        raise FrameworkError("empty compatibility mirror list")
    return {"mirror_pairs": len(seen), "verified_files": total,
            "status": "SOURCE_MIRRORS_IDENTICAL"}
