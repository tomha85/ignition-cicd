#!/usr/bin/env python3
"""Sync Generic EAM choice lists from factory manifests, without changing legacy UI.

GitHub workflow_dispatch choices are static at dispatch time; each factory /
project combination is verified after selection. A listed factory is not an
authorization to deploy.
"""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError
from scripts.sync_workflow_choices import collect_choices, render

WORKFLOW = Path(".github/workflows/generic-eam-e2e-test.yml")


def sync(root: Path, check: bool = False) -> bool:
    file = root / WORKFLOW
    current = file.read_text(encoding="utf-8")
    factories, projects = collect_choices(root / "factories")
    result = render(current, factories, projects)
    if result == current:
        print(f"GENERIC_EAM_CHOICES_SYNCED: {len(factories)} factories, {len(projects)} projects")
        return True
    if check:
        print("HOLD: generic EAM dropdown differs from registered factory manifests", file=sys.stderr)
        return False
    file.write_text(result, encoding="utf-8")
    print(f"GENERIC_EAM_CHOICES_UPDATED: {len(factories)} factories, {len(projects)} projects")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return 0 if sync(ROOT, args.check) else 2
    except (FrameworkError, OSError, ValueError, UnicodeError) as exc:
        print("HOLD: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
