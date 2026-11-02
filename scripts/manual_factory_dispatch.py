#!/usr/bin/env python3
"""Select any manifest-verified Factory/Project; stage only on commissioned TEST target."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError, plan_release, validate_catalog
from framework.deployment.planner import resolve_project_gateway
from framework.security.policies import resolve_controller_stage_target


def select(factory, gateway, project, sha):
    if not isinstance(project, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", project):
        raise FrameworkError("invalid project name")
    catalog = ROOT / "factories"
    validate_catalog(catalog)
    gateway = gateway if gateway is not None else resolve_project_gateway(ROOT, factory, project)
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
    return resolve_controller_stage_target(ROOT, factory, gateway, project)


def main():
    parser = argparse.ArgumentParser(description="Manual factory TEST selector")
    parser.add_argument("--action", choices=["validate", "stage-controller"], required=True)
    parser.add_argument("--factory", required=True)
    parser.add_argument("--gateway", default=None, help="legacy explicit Gateway (optional)")
    parser.add_argument("--github-output", default=None, help="validated GitHub job output file")
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        plan = select(args.factory, args.gateway, args.project, args.sha)
        if args.action == "validate":
            eligible = resolve_controller_stage_target(
                ROOT, plan["factory_id"], plan["gateway_id"], plan["project"],
                require_approved=False,
            ) is not None
            if args.github_output:
                with open(args.github_output, "a", encoding="utf-8") as output:
                    output.write("gateway_id=" + plan["gateway_id"] + "\n")
                    output.write("stage_eligible=" + str(eligible).lower() + "\n")
            print(json.dumps(plan, indent=2))
            print("RESOLVED_TEST_GATEWAY=" + plan["gateway_id"])
            if not eligible:
                print("TEST_CONTROLLER_STAGE=NOT_COMMISSIONED_VALIDATE_ONLY")
            return 0
        authorize_stage(plan["factory_id"], plan["gateway_id"], plan["project"])
        # The generic adapter independently rechecks manifest/TEST target,
        # current-run reviewer approval, backup, source hashes and Controller scan.
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/stage_selected_test_controller.py"),
             "--factory", plan["factory_id"], "--gateway", plan["gateway_id"],
             "--project", plan["project"], "--sha", args.sha],
            cwd=ROOT, check=True
        )
        print("SELECTED_FACTORY_CONTROLLER_STAGE=CHECK_EVIDENCE")
        return 0
    except FrameworkError as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
