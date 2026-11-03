"""Regression: candidate E2E cannot bypass reviewed Warehouse LAB protections."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from reusable_cicd.core import FrameworkError
from scripts.authorize_generic_eam_candidate import (
    require_lab_candidate, CANDIDATE_REF)
from scripts.resolve_generic_eam_e2e import verified

ROOT = Path(__file__).resolve().parents[1]
GOOD = {
    "GITHUB_REPOSITORY": "tomha85/ignition-cicd",
    "GITHUB_REF": CANDIDATE_REF,
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "IGNITION_GENERIC_EAM_CANDIDATE": "ISOLATED_TEST_ONLY",
}

class GenericEamE2ETests(unittest.TestCase):
    def test_candidate_matches_original_warehouse_lab(self):
        with patch.dict(os.environ, GOOD, clear=True):
            plan = require_lab_candidate(
                ROOT, "lab-warehouse", "warehouse-main", "WarehouseHMI")
        self.assertEqual(plan["eam_task"], "CICD-SEND-WarehouseHMI-A")
        self.assertFalse(plan["production_approved"])

    def test_read_only_validate_resolves_registered_lab(self):
        plan = verified("lab-warehouse", "WarehouseHMI")
        self.assertEqual(plan["agent_name"], "EAM-Agent")

    def test_bad_environment_or_branch_refused(self):
        for field, value in (
            ("GITHUB_REF", "refs/heads/main"),
            ("GITHUB_REF", "refs/heads/unknown"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("IGNITION_GENERIC_EAM_CANDIDATE", "NO"),
            ("GITHUB_REPOSITORY", "other/repo"),
        ):
            with self.subTest(field=field, value=value):
                with patch.dict(os.environ, dict(GOOD, **{field:value}), clear=True):
                    with self.assertRaises(FrameworkError):
                        require_lab_candidate(
                            ROOT, "lab-warehouse", "warehouse-main", "WarehouseHMI")

    def test_uncommissioned_project_refused(self):
        with patch.dict(os.environ, GOOD, clear=True):
            with self.assertRaises(FrameworkError):
                require_lab_candidate(
                    ROOT, "lab-warehouse", "warehouse-main", "FactoryASmoke")

    def test_other_factory_refused(self):
        with patch.dict(os.environ, GOOD, clear=True):
            with self.assertRaises(FrameworkError):
                require_lab_candidate(
                    ROOT, "lab-packaging", "packaging-main", "PackagingLineHMI")

    def test_needs_reviewed_environment_and_no_unapproved_stage(self):
        s = (ROOT / ".github/workflows/generic-eam-e2e-test.yml").read_text()
        self.assertIn("environment: ignition-test", s)
        self.assertIn("needs: validate", s)
        self.assertIn("scripts/verify_stage_approval.py", s)
        self.assertIn("IGNITION_GENERIC_EAM_CANDIDATE: ISOLATED_TEST_ONLY", s)
        self.assertIn("scripts/auto_send_existing_eam_task.py", s)
        self.assertIn("scripts/manual_factory_dispatch.py", s)
        self.assertIn("github.event_name == 'workflow_dispatch'", s)
        self.assertNotIn("production_approved: true", s)

if __name__ == "__main__":
    unittest.main()
