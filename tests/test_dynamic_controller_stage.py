"""Deterministic security and qualification tests for generic LAB Controller staging."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reusable_cicd.core import FrameworkError
from framework.security.policies import (
    check_target_registry, resolve_controller_stage_target,
)
from scripts.manual_factory_dispatch import authorize_stage, select
from scripts import stage_selected_test_controller as generic

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


class DynamicControllerStageTests(unittest.TestCase):
    def test_both_warehouse_projects_use_same_approved_controller(self):
        for project in ("WarehouseHMI", "FactoryASmoke"):
            with self.subTest(project=project):
                report = select("lab-warehouse", None, project, SHA)
                self.assertEqual(report["gateway_id"], "warehouse-main")
                target = authorize_stage("lab-warehouse", "warehouse-main", project)
                self.assertEqual(target["controller_id"], "ignition-eam-controller")
                self.assertEqual(target["agent_id"], "ignition-eam-agent")
                self.assertEqual(target["project_scope"], "all_manifest_projects")
                self.assertTrue(target["controller_stage_approved"])
                self.assertFalse(target["eam_send_commissioned"])
                self.assertFalse(target["production_approved"])
                parsed, source, expected = generic.prepare(
                    "lab-warehouse", "warehouse-main", project, SHA
                )
                self.assertEqual(parsed, target)
                self.assertTrue(source.is_dir())
                self.assertTrue(expected)
                self.assertEqual(source.name, project)

    def test_uncommissioned_factories_must_remain_validate_only(self):
        choices = (
            ("lab-assembly", "assembly-main", "ConveyorHMI"),
            ("lab-packaging", "packaging-main", "PackagingLineHMI"),
        )
        for factory, gateway, project in choices:
            with self.subTest(factory=factory):
                self.assertIsNone(resolve_controller_stage_target(
                    ROOT, factory, gateway, project, require_approved=False
                ))
                with self.assertRaisesRegex(FrameworkError, "VALIDATE ONLY"):
                    authorize_stage(factory, gateway, project)

    def test_cross_factory_wrong_gateway_and_unknown_project_denied(self):
        for factory, gateway, project in (
            ("lab-warehouse", "assembly-main", "WarehouseHMI"),
            ("lab-warehouse", "warehouse-main", "PackagingLineHMI"),
            ("lab-assembly", "assembly-main", "FactoryASmoke"),
        ):
            with self.subTest(factory=factory, gateway=gateway):
                with self.assertRaises(FrameworkError):
                    authorize_stage(factory, gateway, project)

    def test_ambiguous_gateway_denied_even_when_explicitly_selected(self):
        with self.assertRaisesRegex(FrameworkError, "AMBIGUOUS_GATEWAY"):
            generic.prepare("lab-assembly", "assembly-main", "PackagingHMI", SHA)

    def test_approved_scope_requires_real_local_controller_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "factories", root / "factories")
            (root / "targets").mkdir()
            target = json.loads((ROOT / "targets/lab-targets.json").read_text())
            def check_with_changes(**changes):
                record = target["targets"][0]
                prior = {k: record.get(k) for k in changes}
                record.update(changes)
                (root / "targets/lab-targets.json").write_text(json.dumps(target))
                try:
                    with self.assertRaises(FrameworkError):
                        check_target_registry(root)
                finally:
                    record.update(prior)
            check_with_changes(environment="production")
            check_with_changes(controller_scan_url="https://plc.example.com/data/api/v1/scan/projects")
            check_with_changes(controller_scan_url="http://localhost:9143/data/api/v1/scan/projects")
            check_with_changes(controller_id="../../../etc")
            check_with_changes(project_scope="single-hardcoded-project")
            check_with_changes(eam_send_commissioned=True)
            check_with_changes(production_approved=True)
            check_with_changes(agent_id="ignition-eam-controller")

    def test_no_stage_without_explicit_lab_confirm_or_environment(self):
        for project in ("FactoryASmoke", "WarehouseHMI"):
            with self.subTest(project=project):
                with patch.dict(os.environ, {"IGNITION_TEST_STAGE_CONFIRM": ""}):
                    with patch.object(generic, "execute") as execute:
                        with self.assertRaisesRegex(FrameworkError, "confirmation"):
                            generic.stage("lab-warehouse", "warehouse-main", project, SHA)
                        execute.assert_not_called()

    def test_no_fake_success_in_read_only_plan(self):
        for project in ("WarehouseHMI", "FactoryASmoke"):
            result = select("lab-warehouse", None, project, SHA)
            self.assertEqual(result["controller_stage"], "NOT_RUN")
            self.assertEqual(result["eam_send_project"], "NOT_RUN")
            self.assertEqual(result["browser_render"], "NOT_TESTED")
            self.assertFalse(result["production_approved"])
            self.assertFalse(result["deployment_authorized"])

    def test_workflow_has_exactly_two_jobs_review_required(self):
        wf = (ROOT / ".github/workflows/ignition-eam-multi-factory.yml").read_text()
        import re
        jobs = re.findall(r"^  ([a-z][a-z0-9-]*):$", wf.split("jobs:", 1)[1], re.M)
        self.assertEqual(jobs, ["validate", "stage-controller"])
        self.assertIn("environment: ignition-test", wf)
        self.assertIn("needs.validate.outputs.stage_eligible == 'true'", wf)
        self.assertIn("scripts/verify_stage_approval.py", wf)
        self.assertIn("scripts/manual_factory_dispatch.py", wf)
        self.assertNotIn("FACTORY_A_SMOKE_CONFIRM", wf)
        self.assertIn("needs.validate.outputs.controller_id", wf)
        self.assertIn("needs.validate.outputs.agent_id", wf)
        self.assertNotIn("IGNITION_CONTROLLER_CONTAINER: 'ignition-eam-controller'", wf)
        self.assertNotIn("IGNITION_AGENT_CONTAINER: 'ignition-eam-agent'", wf)
        self.assertNotIn("options: [FactoryASmoke", wf)

if __name__ == "__main__":
    unittest.main()
