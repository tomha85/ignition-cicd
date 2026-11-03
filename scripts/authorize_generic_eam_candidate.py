"""Strict activation contract for the isolated generic EAM E2E candidate.

Does not authorize arbitrary targets. Only the existing commissioned Warehouse LAB
can be exercised on the reviewed candidate branch; original main stays unchanged.
"""
from __future__ import annotations
import os
from pathlib import Path
from reusable_cicd.core import FrameworkError
from framework.deployment.generic_eam import resolve
from framework.security.policies import resolve_controller_stage_target

CANDIDATE_REF = "refs/heads/feat/generic-multifactory-eam-engine-v1-20261103"
FACTORY = "lab-warehouse"
GATEWAY = "warehouse-main"
PROJECT = "WarehouseHMI"
RUNNER = ["self-hosted", "linux", "ignition-lab"]
CONTROLLER_URL = "https://localhost:9143"

def require_lab_candidate(root: Path, factory: str, gateway: str,
                          project: str, context=None) -> dict:
    context = os.environ if context is None else context
    if (context.get("GITHUB_REF") != CANDIDATE_REF or
            context.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or
            context.get("GITHUB_REPOSITORY") != "tomha85/ignition-cicd" or
            context.get("IGNITION_GENERIC_EAM_CANDIDATE") != "ISOLATED_TEST_ONLY"):
        raise FrameworkError("HOLD: invalid generic candidate execution context")
    if (factory, gateway, project) != (FACTORY, GATEWAY, PROJECT):
        raise FrameworkError("HOLD: generic live candidate only commissioned for Warehouse TEST")
    plan = resolve(root, factory, project, gateway=gateway)
    trusted = resolve_controller_stage_target(root, factory, gateway, project)
    tasks = trusted.get("eam_tasks", [])
    if (plan["target_id"] != trusted["target_id"] or
            plan["controller_id"] != trusted["controller_id"] or
            plan["agent_id"] != trusted["agent_id"] or
            plan["eam_task"] not in [t["task_name"] for t in tasks
                                    if t["project"] == project] or
            trusted["eam_send_commissioned"] is not True or
            plan["runner_labels"] != RUNNER or
            plan["controller_api_base_url"] != CONTROLLER_URL or
            plan["github_environment"] != "ignition-test" or
            trusted["controller_scan_url"] != CONTROLLER_URL + "/data/api/v1/scan/projects"):
        raise FrameworkError("HOLD: generic plan differs from commissioned LAB identity")
    return plan

def main():
    import argparse, json, sys
    parser=argparse.ArgumentParser()
    parser.add_argument("--factory",required=True)
    parser.add_argument("--gateway",required=True)
    parser.add_argument("--project",required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(require_lab_candidate(
            Path(__file__).resolve().parents[1],
            args.factory,args.gateway,args.project), indent=2))
        return 0
    except FrameworkError as exc:
        print(str(exc),file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
