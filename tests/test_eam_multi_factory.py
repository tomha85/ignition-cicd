import importlib.util
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("eam_multi_factory", ROOT/"scripts/eam_multi_factory.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class MultiFactoryTests(unittest.TestCase):
    def test_three_projects_are_independent(self):
        cfg=mod.validate_registry()
        self.assertEqual(set(cfg["targets"]),set(mod.REQUIRED))
        self.assertEqual(len({x["project"] for x in cfg["targets"].values()}),3)
        self.assertEqual(len({x["agent"] for x in cfg["targets"].values()}),3)
        self.assertEqual(len({x["task"] for x in cfg["targets"].values()}),3)

    def test_release_is_target_scoped(self):
        plan=mod.release_plan("factory_b", "a"*40)
        self.assertEqual(plan["project"],"ConveyorHMI")
        self.assertEqual(plan["eam_task"],"CICD-SEND-ConveyorHMI-B")
        self.assertEqual(plan["deployment"],"HOLD")

    def test_unknown_factory_rejected(self):
        with self.assertRaises(RuntimeError):
            mod.release_plan("factory_d","a"*40)

if __name__=="__main__":
    unittest.main()
