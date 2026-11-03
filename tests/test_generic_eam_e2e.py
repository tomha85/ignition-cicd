"""Regression: candidate E2E cannot bypass reviewed Warehouse LAB protections."""
import os
import subprocess
import sys
import tempfile
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

    def test_authorizer_is_executable_from_foreign_working_directory(self):
        # Reproduce GitHub runner: python scripts/authorize_generic_eam_candidate.py
        # must bootstrap repository imports even if PYTHONPATH is unset.
        script = ROOT / "scripts/authorize_generic_eam_candidate.py"
        with tempfile.TemporaryDirectory() as other_dir:
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.update(GOOD)
            proc = subprocess.run(
                [sys.executable, str(script),
                 "--factory", "lab-warehouse",
                 "--gateway", "warehouse-main",
                 "--project", "WarehouseHMI"],
                cwd=other_dir, env=environment, text=True,
                capture_output=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"eam_task": "CICD-SEND-WarehouseHMI-A"', proc.stdout)

    def test_main_branch_is_explicitly_authorized_only_in_isolated_lab(self):
        approved = dict(GOOD, GITHUB_REF="refs/heads/main")
        with patch.dict(os.environ, approved, clear=True):
            plan = require_lab_candidate(
                ROOT, "lab-warehouse", "warehouse-main", "WarehouseHMI")
        self.assertEqual(plan["eam_task"], "CICD-SEND-WarehouseHMI-A")
        refused = dict(approved, IGNITION_GENERIC_EAM_CANDIDATE="NO")
        with patch.dict(os.environ, refused, clear=True):
            with self.assertRaises(FrameworkError):
                require_lab_candidate(
                    ROOT, "lab-warehouse", "warehouse-main", "WarehouseHMI")

    def test_generic_main_deployment_still_requires_approval(self):
        workflow = (ROOT / ".github/workflows/generic-eam-e2e-test.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("environment: ignition-test", workflow)
        self.assertIn("scripts/verify_stage_approval.py", workflow)
        self.assertIn("needs: validate", workflow)
        self.assertIn("IGNITION_GENERIC_EAM_CANDIDATE: ISOLATED_TEST_ONLY", workflow)
        staging = (ROOT / "scripts/stage_selected_test_controller.py").read_text()
        sending = (ROOT / "scripts/auto_send_existing_eam_task.py").read_text()
        for content in (staging, sending):
            self.assertIn('os.getenv("IGNITION_GENERIC_EAM_CANDIDATE") == "ISOLATED_TEST_ONLY"', content)
            self.assertIn("require_lab_candidate(ROOT, factory, gateway, project)", content)

    def test_read_only_validate_resolves_registered_lab(self):
        plan = verified("lab-warehouse", "WarehouseHMI")
        self.assertEqual(plan["agent_name"], "EAM-Agent")

    def test_bad_environment_or_branch_refused(self):
        for field, value in (
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
