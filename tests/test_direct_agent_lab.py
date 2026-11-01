"""Safety checks for direct Agent TEST deployment candidate."""
import subprocess
import importlib.util
from unittest.mock import patch
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DirectAgentCandidateTests(unittest.TestCase):
    def test_default_invocation_fails_closed(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/direct_agent_lab.py")],
                              cwd=str(ROOT), text=True, capture_output=True, timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("TEST-only gate", proc.stderr)

    def test_requires_agent_https_and_ca(self):
        code = (ROOT / "scripts/direct_agent_lab.py").read_text()
        self.assertIn("ssl.create_default_context(cafile=", code)
        self.assertIn("https://localhost:9243/data/api/v1/scan/projects", code)
        self.assertNotIn("verify=False", code)
        self.assertNotIn("http://localhost:9288/data/api", code)

    def test_backups_before_replacement(self):
        code = (ROOT / "scripts/direct_agent_lab.py").read_text()
        self.assertLess(code.index("project_backups"), code.index('run("docker", "cp",'))
        self.assertIn("verify_full_gateway_backup()", code)
        self.assertIn("browser_version(expected)", code)
        self.assertIn("IGNITION_E2E_BROWSER", code)
        self.assertIn("webdriver.Chrome", code)
        self.assertIn("webdriver.Edge", code)
        self.assertIn("webdriver.Firefox", code)
        self.assertNotIn('shutil.which("firefox")', code)
        self.assertIn("rollback_runtime", code)
        self.assertNotIn("HOLD: native Perspective runtime verification not qualified", code)

    def test_scan_wait_requires_new_completed_timestamp(self):
        spec = importlib.util.spec_from_file_location(
            "direct_agent_lab", ROOT / "scripts/direct_agent_lab.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        responses = iter([
            {"scanActive": False, "lastScanTimestamp": 100},
            {"scanActive": True, "lastScanTimestamp": 100},
            {"scanActive": False, "lastScanTimestamp": 101},
        ])
        with patch.object(module, "scan_api", side_effect=lambda *a: next(responses)):
            with patch.object(module.time, "sleep", return_value=None):
                result = module.wait_scan("test", "masked", None, baseline_timestamp=100)
        self.assertEqual(result["lastScanTimestamp"], 101)

    def test_rollback_hashes_and_browser_preflight_exist(self):
        code = (ROOT / "scripts/direct_agent_lab.py").read_text()
        self.assertLess(code.index("browser_probe = make_browser()"),
                        code.index('run("docker", "cp",'))
        self.assertIn("remote_hashes(files, dst) != old_hashes", code)
        self.assertIn("baseline_timestamp=initial_scan", code)

    def test_no_auto_push_release(self):
        wf = (ROOT / ".github/workflows/ignition-e2e.yml").read_text()
        self.assertIn("inputs.action == 'deploy-agent-direct'", wf)
        self.assertIn("IGNITION_AGENT_API_TOKEN", wf)
        self.assertIn("ignition-test-direct-evidence", wf)
        self.assertIn("IGNITION_AGENT_GWBK", wf)
        self.assertIn("IGNITION_E2E_BROWSER", wf)
        self.assertIn("default: deploy-agent-direct", wf)
        self.assertIn("github.ref == 'refs/heads/main'", wf)
        self.assertNotIn("IGNITION_TEST_AUTO_DIRECT", wf)


if __name__ == "__main__":
    unittest.main()
