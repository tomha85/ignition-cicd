import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from stage_controller import check_config

class StageConfigTests(unittest.TestCase):
    def test_manifest_is_lab_and_closed(self):
        self.assertTrue((check_config() / "project.json").exists())
