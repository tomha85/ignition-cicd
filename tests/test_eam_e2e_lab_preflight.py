"""EAM preflight is read-only, deterministic and blocks uncommissioned EAM."""
import unittest
import os
from unittest.mock import patch
from scripts.eam_e2e_lab_preflight import preflight

SHA = "a" * 40

class EamPreflightTests(unittest.TestCase):
    def test_unsafe_eam_tasks_never_become_pass(self):
        with patch.dict(os.environ, {
            "IGNITION_EAM_BRIDGE_COMMISSIONED": "NO",
            "IGNITION_FACTORY_A_SMOKE_TASK_COMMISSIONED": "NO",
        }):
            plan = preflight(SHA, False)
        self.assertEqual(plan["status"], "HOLD")
        self.assertIn("EAM_SEND_NOT_COMMISSIONED_IN_TARGET_REGISTRY", plan["blockers"])
        self.assertIn("EAM_CONTROLLER_BRIDGE_NOT_ATTESTED", plan["blockers"])
        self.assertIn("FACTORY_A_SMOKE_SEND_PROJECT_TASK_NOT_ATTESTED", plan["blockers"])
        self.assertEqual(plan["eam_send_project"], "NOT_RUN")
        self.assertEqual(plan["perspective_browser"], "NOT_TESTED")

    def test_env_flags_alone_cannot_override_registry_hold(self):
        with patch.dict(os.environ, {
            "IGNITION_EAM_BRIDGE_COMMISSIONED": "YES",
            "IGNITION_FACTORY_A_SMOKE_TASK_COMMISSIONED": "YES",
        }):
            plan = preflight(SHA, False)
        self.assertIn("EAM_SEND_NOT_COMMISSIONED_IN_TARGET_REGISTRY", plan["blockers"])

    def test_never_accepts_short_sha(self):
        with self.assertRaises(ValueError):
            preflight("short", False)

if __name__ == "__main__":
    unittest.main()
