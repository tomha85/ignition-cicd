#!/usr/bin/env python3
"""Generate native GitHub Actions choice dropdowns from versioned factory manifests.

GitHub's workflow_dispatch choice list is resolved when workflow YAML is loaded,
so it cannot make a second dropdown depend on the first one at runtime.
This generator is the sole source for BOTH global choices lists. The dispatch
adapter validates factory/project membership and rejects ambiguous mappings.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError, discover_factories, load_factory

WORKFLOW = Path(".github/workflows/ignition-eam-multi-factory.yml")
MAX_CHOICES = 100
FACTORY_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
PROJECT_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
MARKERS = {
    "factory": ("        # BEGIN GENERATED FACTORY OPTIONS\n",
                "        # END GENERATED FACTORY OPTIONS\n"),
    "project": ("        # BEGIN GENERATED PROJECT OPTIONS\n",
                "        # END GENERATED PROJECT OPTIONS\n"),
}
PREFERRED_DEFAULTS = {"factory": "lab-warehouse", "project": "WarehouseHMI"}


def collect_choices(factories: Path) -> tuple[list[str], list[str]]:
    factory_names = sorted(discover_factories(factories))
    if not factory_names:
        raise FrameworkError("no registered factories")
    project_names: set[str] = set()
    for factory in factory_names:
        if not FACTORY_PATTERN.fullmatch(factory):
            raise FrameworkError("unsafe factory choice")
        manifest = load_factory(factories, factory)
        if manifest.get("factory_id") != factory:
            raise FrameworkError("factory manifest ID mismatch")
        for gateway in manifest["gateways"]:
            for record in gateway["projects"]:
                name = record["name"]
                if not isinstance(name, str) or not PROJECT_PATTERN.fullmatch(name):
                    raise FrameworkError("unsafe project choice")
                project_names.add(name)
    if not project_names:
        raise FrameworkError("no registered projects")
    for title, items in (("factory", factory_names), ("project", project_names)):
        if len(items) > MAX_CHOICES:
            raise FrameworkError(
                f"too many {title} dropdown options ({len(items)}); "
                "use a dedicated dynamic UI rather than silently dropping projects"
            )
    return factory_names, sorted(project_names)


def prioritized(choices: list[str], preferred: str) -> list[str]:
    return ([preferred] if preferred in choices else []) + [
        item for item in choices if item != preferred
    ]


def replace_region(workflow: str, kind: str, options: list[str]) -> str:
    begin, end = MARKERS[kind]
    if workflow.count(begin) != 1 or workflow.count(end) != 1:
        raise FrameworkError(f"missing or duplicate {kind} generated markers")
    before, rest = workflow.split(begin, 1)
    _, after = rest.split(end, 1)
    new_list = "        options:\n" + "".join(f"          - {item}\n" for item in options)
    return before + begin + new_list + end + after


def render(workflow: str, factory_choices: list[str], project_choices: list[str]) -> str:
    results = workflow
    for kind, choices in (("factory", factory_choices), ("project", project_choices)):
        preferred = PREFERRED_DEFAULTS[kind]
        if preferred not in choices:
            raise FrameworkError(
                f"{kind} default {preferred} is missing; review/select a new default"
            )
        results = replace_region(results, kind, prioritized(choices, preferred))
    return results


def sync(root: Path, check: bool = False) -> bool:
    workflow_path = root / WORKFLOW
    factories = root / "factories"
    current = workflow_path.read_text(encoding="utf-8")
    choices = collect_choices(factories)
    target = render(current, *choices)
    if current == target:
        print("GITHUB_DROPDOWNS_SYNCED: factory=" + str(len(choices[0])) +
              " project=" + str(len(choices[1])))
        return True
    if check:
        print("HOLD: GitHub dropdowns differ from factories/*/factory.json. "
              "Run: python scripts/sync_workflow_choices.py, commit the YAML.",
              file=sys.stderr)
        return False
    workflow_path.write_text(target, encoding="utf-8")
    print("GITHUB_DROPDOWNS_UPDATED: factory=" + str(len(choices[0])) +
          " project=" + str(len(choices[1])))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="read-only CI drift check")
    args = parser.parse_args()
    try:
        return 0 if sync(ROOT, check=args.check) else 2
    except (FrameworkError, OSError, UnicodeError, ValueError) as exc:
        print("HOLD: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
