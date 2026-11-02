"""Contract checks for TEST-only multi-factory EAM deploy adapter."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "eam_multi_factory_deploy", ROOT / "scripts/eam_multi_factory_deploy.py")
import sys
sys.path.insert(0, str(ROOT / "scripts"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class EAMDeployTests(unittest.TestCase):
    def test_agents_are_three_distinct_containers(self):
        self.assertEqual(len(set(mod.CONTAINERS.values())), 3)
        self.assertEqual(set(mod.CONTAINERS), {"factory_a","factory_b","factory_c"})

    def test_no_gate_no_deploy(self):
        with patch.dict(mod.os.environ, {"IGNITION_EAM_LAB_ONLY":"NO"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "TEST-only"):
                mod.preflight("factory_a")

    def test_missing_bridge_fails_closed(self):
        with patch.dict(mod.os.environ, {"IGNITION_EAM_LAB_ONLY":"YES"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "bridge"):
                mod.preflight("factory_b")

    def test_backups_before_controller_mutation(self):
        source = (ROOT / "scripts/eam_multi_factory_deploy.py").read_text()
        self.assertLess(source.index('plan["backup_verified"] = True'),
                        source.index('run("docker", "cp", str(src)'))
        self.assertIn('plan["eam_task_status"] = "REPORTED_COMPLETED"', source)
        self.assertIn('plan["agent_verification"] = "FILES_MATCH"', source)
        self.assertIn('plan["e2e_rendered"] = "NOT_TESTED"', source)
        self.assertNotIn('DEPLOYMENT=PASS', source)

if __name__ == "__main__":
    unittest.main()
