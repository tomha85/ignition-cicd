"""Safety checks for direct Agent TEST deployment candidate."""
import subprocess
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
        self.assertIn("rollback_runtime", code)
        self.assertNotIn("HOLD: native Perspective runtime verification not qualified", code)

    def test_no_auto_push_release(self):
        wf = (ROOT / ".github/workflows/ignition-e2e.yml").read_text()
        self.assertIn("inputs.action == 'deploy-agent-direct'", wf)
        self.assertIn("IGNITION_AGENT_API_TOKEN", wf)
        self.assertIn("ignition-direct-agent-evidence", wf)
        self.assertIn("IGNITION_AGENT_GWBK", wf)
        self.assertIn("IGNITION_TEST_AUTO_DIRECT", wf)


if __name__ == "__main__":
    unittest.main()
