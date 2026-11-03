#!/usr/bin/env python3
"""Resolve the generic candidate's uniquely commissioned TEST target without writes."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework.deployment.generic_eam import resolve
from framework.security.policies import resolve_controller_stage_target
from framework.validation.structure import qualify_repository

def verified(factory, project):
    qualify_repository(ROOT)
    plan = resolve(ROOT, factory, project)
    target = resolve_controller_stage_target(
        ROOT, factory, plan["gateway_id"], project)
    approved = [x for x in target.get("eam_tasks", [])
                if x.get("project") == project and
                   x.get("task_name") == plan["eam_task"] and
                   x.get("agent_name") == plan["agent_name"]]
    if (target.get("eam_send_commissioned") is not True or
            len(approved) != 1 or
            plan["target_id"] != target["target_id"] or
            plan["controller_id"] != target["controller_id"] or
            plan["agent_id"] != target["agent_id"] or
            plan["runner_labels"] != ["self-hosted", "linux", "ignition-lab"] or
            plan["github_environment"] != "ignition-test" or
            plan["controller_api_base_url"] != "https://localhost:9143"):
        raise RuntimeError("HOLD: generic target does not match commissioned LAB")
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
            for key, val in {
                    "gateway_id": plan["gateway_id"],
                    "controller_id": plan["controller_id"],
                    "agent_id": plan["agent_id"],
                    "task_name": plan["eam_task"],
                    "stage_eligible": "true"}.items():
                stream.write(key + "=" + val + "\n")
        print(json.dumps(plan, indent=2))
        return 0
    except Exception as exc:
        print("GENERIC_EAM_HOLD: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
