"""CI tests proving the auto-deployment gates fail closed until native resource proof."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ControllerAutomationSafetyTests(unittest.TestCase):
    def test_native_timer_qualification_is_hold(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/check_controller_timer.py")],
            cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HOLD:", result.stderr)

    def test_manifest_disables_automatic_eam_until_native_proof(self):
        manifest = json.loads((ROOT / "manifests/ignition-test.json").read_text())
        self.assertIs(manifest["automatic_eam_enabled"], False)
        self.assertIs(manifest["production_approved"], False)
        self.assertEqual(manifest["eam_task"], "CICD-AUTO-DeploymentSmokeTest")
        self.assertTrue(manifest["requires_gateway_scan"])
        self.assertTrue(manifest["requires_runtime_smoke"])

    def test_deployer_uses_verified_tls_not_plaintext(self):
        src = (ROOT / "scripts/auto_eam_lab.py").read_text()
        self.assertIn("ssl.create_default_context(cafile=", src)
        self.assertIn("https://localhost:9143/data/api/v1/scan/projects", src)
        self.assertNotIn("http://127.0.0.1:9188/data/api/v1/scan/projects", src)
        self.assertIn('validate_native_controller_timer()', src)
        self.assertIn('IGNITION_CONTROLLER_RUNTIME_VERIFIED_SHA', src)

    def test_controller_only_trigger_and_consistent_task(self):
        trigger = (ROOT / "controller/eam_trigger_gateway_timer.py").read_text()
        manifest = json.loads((ROOT / "manifests/ignition-test.json").read_text())
        self.assertIn("system.eam.runTask", trigger)
        self.assertIn(manifest["eam_task"], trigger)

    def test_push_deploy_is_opt_in(self):
        workflow = (ROOT / ".github/workflows/ignition-e2e.yml").read_text()
        self.assertIn("IGNITION_TEST_AUTO_DEPLOY", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("IGNITION_GATEWAY_API_TOKEN", workflow)


if __name__ == "__main__":
    unittest.main()
