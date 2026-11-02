"""Stamp a TEST Controller staging copy, never the Git-tracked project.

The description states STAGED (not deployed). Content hash is computed from
source project bytes, independent of Git SHA and run ID.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def stamp(project_dir: Path, factory: str, release_sha: str, run_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", release_sha):
        raise ValueError("HOLD: invalid full Git SHA")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("HOLD: invalid GitHub run ID")
    project_file = project_dir / "project.json"
    data = json.loads(project_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("title"):
        raise ValueError("HOLD: invalid Ignition project.json")
    original = data.get("description", "")
    if not isinstance(original, str):
        raise ValueError("HOLD: invalid description")
    # Remove previous CI-generated suffix on re-staging a stamped copy.
    original = original.split(" | EAM TEST STAGED | ")[0]
    h = hashlib.sha256()
    files = sorted(p for p in project_dir.rglob("*") if p.is_file())
    for p in files:
        if p.is_symlink():
            raise ValueError("HOLD: symlinked project resource")
        relative = p.relative_to(project_dir).as_posix()
        h.update(relative.encode("utf-8") + b"\\0")
        if p == project_file:
            content_data = dict(data)
            content_data["description"] = original
            h.update(json.dumps(content_data, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        else:
            h.update(p.read_bytes())
        h.update(b"\\0")
    digest = h.hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data["description"] = (
        f"{original} | EAM TEST STAGED | factory={factory} | "
        f"source={release_sha[:12]} | content={digest[:16]} | "
        f"run={run_id} | at={timestamp} | NOT AGENT VERIFIED"
    )
    project_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"project": data["title"], "factory": factory,
            "release_sha": release_sha, "source_content_sha256": digest,
            "github_run_id": run_id, "staged_at_utc": timestamp,
            "controller_status": "STAGING_ONLY", "agent_verification": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--factory", choices=["factory_a", "factory_b", "factory_c"], required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(stamp(Path(args.project_dir), args.factory, args.sha, args.run_id), indent=2))


if __name__ == "__main__":
    main()
