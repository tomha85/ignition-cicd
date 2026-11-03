#!/usr/bin/env python3
"""Resolve any registered Factory/Project; authorize EAM only when commissioned.

A visible dropdown choice does not grant deployment permission. Uncommissioned
Factory/Gateway/Project combinations produce VALIDATE_ONLY rather than a fake
Agent deployment success. Ambiguous/invalid manifest associations fail closed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError
from scripts.manual_factory_dispatch import select
from framework.deployment.generic_eam import resolve
from framework.security.policies import resolve_controller_stage_target
from framework.validation.structure import qualify_repository


def verified(factory, project):
    qualify_repository(ROOT)
    selection = select(factory, None, project, "a" * 40)
    gateway = selection["gateway_id"]
    target = resolve_controller_stage_target(
        ROOT, factory, gateway, project, require_approved=False)
    if not target or target.get("eam_send_commissioned") is not True:
        return {
            "status": "VALIDATED_NOT_COMMISSIONED",
            "factory_id": factory, "gateway_id": gateway, "project": project,
            "stage_eligible": False, "deployment_authorized": False,
            "production_approved": False}
    matches = [x for x in target.get("eam_tasks", []) if x.get("project") == project]
    if not matches:
        return {
            "status": "VALIDATED_EAM_TASK_NOT_COMMISSIONED",
            "factory_id": factory, "gateway_id": gateway, "project": project,
            "stage_eligible": False, "deployment_authorized": False,
            "production_approved": False}
    if len(matches) != 1:
        raise FrameworkError("HOLD: ambiguous EAM task registration")
    plan = resolve(ROOT, factory, project, gateway=gateway)
    approved = matches[0]
    if (approved.get("task_name") != plan["eam_task"] or
            approved.get("agent_name") != plan["agent_name"] or
            plan["target_id"] != target["target_id"] or
            plan["controller_id"] != target["controller_id"] or
            plan["agent_id"] != target["agent_id"]):
        raise FrameworkError("HOLD: generic target differs from trusted TEST registry")
    # Current LIVE adapter/runner is commissioned for WarehouseHMI alone.
    if (factory, gateway, project) != ("lab-warehouse", "warehouse-main", "WarehouseHMI"):
        return {
            "status": "VALIDATED_NOT_LIVE_COMMISSIONED",
            "factory_id": factory, "gateway_id": gateway, "project": project,
            "stage_eligible": False, "deployment_authorized": False,
            "production_approved": False}
    if (plan["runner_labels"] != ["self-hosted", "linux", "ignition-lab"] or
            plan["github_environment"] != "ignition-test" or
            plan["controller_api_base_url"] != "https://localhost:9143"):
        raise FrameworkError("HOLD: generic plan differs from commissioned LAB runner/environment/endpoint")
    plan["stage_eligible"] = True
    return plan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        plan = verified(a.factory, a.project)
        with open(a.output, "a", encoding="utf-8") as stream:
            fields = {
                "gateway_id": plan["gateway_id"],
                "controller_id": plan.get("controller_id", ""),
                "agent_id": plan.get("agent_id", ""),
                "task_name": plan.get("eam_task", ""),
                "stage_eligible": str(plan["stage_eligible"]).lower()}
            for key, value in fields.items():
                stream.write(key + "=" + value + "\n")
        print(json.dumps(plan, indent=2))
        if not plan["stage_eligible"]:
            print("GENERIC_EAM_VALIDATE_ONLY: no Agent deployment authorization")
        return 0
    except Exception as exc:
        print("GENERIC_EAM_HOLD: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
