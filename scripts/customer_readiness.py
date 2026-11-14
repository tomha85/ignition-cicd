#!/usr/bin/env python3
"""Independent, read-only customer onboarding readiness gate.

Never claims live deployment readiness from configuration validation. Checks
whether the user has supplied authentic customer identifiers and Controller
endpoints, validates all native sources, and documents unverified runtime gates.
No network, secrets, backups or EAM tasks are accessed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reusable_cicd.core import FrameworkError  # noqa: E402
from scripts.customer_plan import load_profile, build_plan  # noqa: E402

SHA = re.compile(r"^[0-9a-f]{40}$")
ALWAYS_HOLD = {
    "customer_eam_remote_deployer": "NOT_IMPLEMENTED_OR_NOT_QUALIFIED",
    "eam_controller_api_authorization": "NOT_TESTED",
    "gateway_network_controller_to_agent": "NOT_TESTED",
    "eam_task_binding_and_agent_identity": "NOT_VERIFIED",
    "gateway_backup_and_restore_drill": "NOT_TESTED",
    "agent_project_runtime_and_browser_fat": "NOT_TESTED",
    "production_approval": "HOLD",
}


def detect_template_fields(profile: dict) -> list[str]:
    findings = []
    customer = profile["customer_id"]
    if customer.startswith("example-") or "edit-this" in customer:
        findings.append("customer_id is still an example")
    if profile["schema_version"] == 2:
        for index, controller in enumerate(profile["controllers"]):
            hostname = urlsplit(controller["controller_url"]).hostname or ""
            if hostname == "example.invalid" or hostname.endswith(".example.invalid"):
                findings.append("controllers[{}] uses nonfunctional example hostname".format(index))
        for index, site in enumerate(profile["sites"]):
            if "(example)" in site["display_name"].lower() or site["display_name"].lower().startswith("example "):
                findings.append("sites[{}] display name is a sample".format(index))
        for index, target in enumerate(profile["targets"]):
            if target["factory_id"].startswith("lab-"):
                findings.append("targets[{}] still selects bundled lab factory".format(index))
            if "EXAMPLE" in target["agent_name"].upper():
                findings.append("targets[{}] EAM Agent is an example".format(index))
            if "EXAMPLE" in target["eam_task_name"].upper():
                findings.append("targets[{}] EAM task is an example".format(index))
    else:
        for index, target in enumerate(profile["targets"]):
            eam = target["eam"]
            hostname = urlsplit(eam["controller_url"]).hostname or ""
            if hostname == "example.invalid" or hostname.endswith(".example.invalid"):
                findings.append("targets[{}] uses nonfunctional example hostname".format(index))
            if target["factory_id"].startswith("lab-"):
                findings.append("targets[{}] still selects bundled lab factory".format(index))
    return findings


def assess(root: Path, profile: dict, sha: str) -> dict:
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise FrameworkError("READINESS_HOLD: 40-character source SHA required")
    plan = build_plan(root, profile, sha)
    templates = detect_template_fields(profile)
    return {
        "schema_version": 1,
        "customer_id": profile["customer_id"],
        "source_sha": sha,
        "status": ("CUSTOMER_INPUT_REQUIRED" if templates
                   else "OFFLINE_VALIDATED_REMOTE_DEPLOY_UNQUALIFIED"),
        "source_validation": plan["status"],
        "target_count": plan["target_count"],
        "template_findings": templates,
        "readiness": dict(ALWAYS_HOLD),
        "customer_input_complete": not bool(templates),
        "offline_plan_approved_to_run": True,
        "real_eam_deployment_authorized": False,
        "production_deployment_authorized": False,
        "note": "Read-only configuration+source audit. Not proof of network, EAM or Perspective behavior.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit customer inputs; NEVER authorize an EAM deployment")
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--require-customer-input", action="store_true",
                        help="exit HOLD if sample IDs/URLs/Agent/task remain")
    args = parser.parse_args()
    try:
        profile = load_profile(Path(args.config))
        report = assess(ROOT, profile, args.sha)
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        print(text)
        if args.require_customer_input and not report["customer_input_complete"]:
            print("CUSTOMER_READINESS_HOLD: fill in real customer configuration",
                  file=sys.stderr)
            return 2
        return 0
    except (FrameworkError, ValueError, OSError) as exc:
        # Source errors are expected to be raised; no credentials are included.
        print("CUSTOMER_READINESS_HOLD: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
