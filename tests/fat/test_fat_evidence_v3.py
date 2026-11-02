"""FAT cannot be claimed by a successful source build or Controller scan."""
import unittest
from pathlib import Path
from framework.validation.requirements import check_requirements
from framework.deployment.verify import agent_e2e_verified

ROOT=Path(__file__).resolve().parents[2]

class FatEvidenceTest(unittest.TestCase):
    def test_requirements_not_synthetically_passed(self):
        d=check_requirements(ROOT)
        self.assertTrue(all(x["fat_status"]=="NOT_TESTED" for x in d["factory_requirements"]))
    def test_agent_result_is_not_controller_scan(self):
        self.assertFalse(agent_e2e_verified({"status":"CONTROLLER_STAGED_AND_SCANNED_NO_EAM"}))

if __name__=="__main__":unittest.main()
