#!/usr/bin/env python3
"""Manual multi-factory plan selector. Controller staging has one approved LAB target."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError, plan_release, validate_catalog

APPROVED_STAGE = ("lab-warehouse", "warehouse-main", "FactoryASmoke")


def select(factory, gateway, project, sha):
    if not isinstance(project, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", project):
        raise FrameworkError("invalid project name")
    catalog = ROOT / "factories"
    validate_catalog(catalog)
    plan = plan_release(catalog, factory, gateway, "test", sha)
    matches = [p for p in plan["projects"] if p["name"] == project]
    if len(matches) != 1:
        raise FrameworkError("project not registered to selected factory/Gateway")
    return {
        "factory_id": factory, "gateway_id": gateway, "project": project,
        "environment": "test", "github_environment": plan["github_environment"],
        "target_id": plan["target_id"], "source_sha": sha,
        "source_files": matches[0]["file_count"],
        "source_hashes": matches[0]["sha256"],
        "status": "VALIDATED_NOT_DEPLOYED", "controller_stage": "NOT_RUN",
        "eam_send_project": "NOT_RUN", "browser_render": "NOT_TESTED",
        "production_approved": False, "deployment_authorized": False,
    }


def authorize_stage(factory, gateway, project):
    if (factory, gateway, project) != APPROVED_STAGE:
        raise FrameworkError(
            "HOLD: staging limited to lab-warehouse/warehouse-main/FactoryASmoke; "
            "other factory/Gateway/project combinations are VALIDATE ONLY"
        )


def main():
    parser = argparse.ArgumentParser(description="Manual factory TEST selector")
    parser.add_argument("--action", choices=["validate", "stage-controller"], required=True)
    parser.add_argument("--factory", required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        plan = select(args.factory, args.gateway, args.project, args.sha)
        if args.action == "validate":
            print(json.dumps(plan, indent=2))
            return 0
        authorize_stage(args.factory, args.gateway, args.project)
        # The smoke adapter enforces GitHub branch/event, local LAB containers,
        # verified backups, no-overwrite, HTTPS CA/token and source SHA256.
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/factory_a_controller_smoke.py"),
             "--stage-controller", "--sha", args.sha], cwd=ROOT, check=True
        )
        print("SELECTED_FACTORY_CONTROLLER_STAGE=CHECK_EVIDENCE")
        return 0
    except FrameworkError as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
