"""Independent customer onboarding/readiness status regression tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import load_profile
from scripts.customer_readiness import assess
from tests.test_customer_cleanroom import single_factory_fixture, multi_factory_fixture

ROOT = Path(__file__).resolve().parents[1]
SHA = "b" * 40


class CustomerReadinessTests(unittest.TestCase):
    def test_bundled_example_not_claimed_ready_for_customer(self):
        profile = load_profile(ROOT / "config/customer.json")
        report = assess(ROOT, profile, SHA)
        self.assertEqual(report["status"], "CUSTOMER_INPUT_REQUIRED")
        self.assertFalse(report["customer_input_complete"])
        self.assertGreater(len(report["template_findings"]), 0)
        self.assertFalse(report["real_eam_deployment_authorized"])
        self.assertEqual(report["readiness"]["production_approval"], "HOLD")
        result = json.dumps(report)
        self.assertNotIn("eam.private.example.invalid", result)
        self.assertNotIn("HQ_EAM_API_TOKEN", result)

    def test_portable_customer_one_factory_offline_input_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = single_factory_fixture(root)
            report = assess(root, profile, SHA)
            self.assertEqual(report["status"], "OFFLINE_VALIDATED_REMOTE_DEPLOY_UNQUALIFIED")
            self.assertTrue(report["customer_input_complete"])
            self.assertEqual(report["target_count"], 3)
            self.assertEqual(report["readiness"]["gateway_network_controller_to_agent"],
                             "NOT_TESTED")
            self.assertFalse(report["real_eam_deployment_authorized"])

    def test_multiple_factory_custom_names_no_lab_assumptions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = multi_factory_fixture(root)
            report = assess(root, profile, SHA)
            self.assertTrue(report["customer_input_complete"])
            self.assertEqual(report["target_count"], 2)
            self.assertFalse(report["production_deployment_authorized"])

    def test_wrong_project_in_customer_manifest_holds_readiness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = single_factory_fixture(root)
            profile["targets"][0]["project"] = "Unregistered"
            with self.assertRaises(FrameworkError):
                assess(root, profile, SHA)

    def test_v1_demo_is_also_not_customer_ready(self):
        profile = load_profile(ROOT / "config/example-customer-testlab.json")
        report = assess(ROOT, profile, SHA)
        self.assertEqual(report["status"], "CUSTOMER_INPUT_REQUIRED")
        self.assertFalse(report["customer_input_complete"])

    def test_invalid_source_sha_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = single_factory_fixture(root)
            with self.assertRaisesRegex(FrameworkError, "40-character source SHA"):
                assess(root, profile, "deadbeef")

    def test_lab_only_regression_workflows_are_restricted_to_original_repo(self):
        # On another customer's fork, lab-specific Warehouse fixed fixtures
        # must be skipped; customer-config-ci runs the portable suite instead.
        lab_workflows = [
            "architecture-qualification.yml", "reusable-framework-ci.yml",
            "validate.yml", "build-release.yml", "ignition-e2e.yml",
            "customer-framework-demo.yml", "generic-eam-candidate.yml",
            "generic-eam-e2e-test.yml", "ignition-eam-multi-factory.yml",
        ]
        for name in lab_workflows:
            with self.subTest(workflow=name):
                body = (ROOT / ".github" / "workflows" / name).read_text()
                self.assertIn("if: github.repository == 'tomha85/ignition-cicd'", body)

    def test_customer_workflow_runs_offline_without_lab_ownership(self):
        customer_ci = (ROOT / ".github/workflows/customer-config-ci.yml").read_text()
        self.assertNotIn("github.repository == 'tomha85/ignition-cicd'", customer_ci)
        self.assertIn("scripts/customer_plan.py", customer_ci)
        self.assertIn("scripts/customer_build_release.py", customer_ci)
        self.assertNotIn("scripts/auto_send_existing_eam_task.py", customer_ci)


if __name__ == "__main__":
    unittest.main()
