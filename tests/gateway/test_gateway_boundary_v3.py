"""Static Gateway target safety; these tests cannot create or run an EAM task."""
import unittest
from pathlib import Path
from framework.security.policies import check_target_registry, require_production_authorization
from reusable_cicd.core import FrameworkError

ROOT=Path(__file__).resolve().parents[2]

class GatewayBoundaryTest(unittest.TestCase):
    def test_agent_release_stays_uncommissioned(self):
        registry=check_target_registry(ROOT)
        self.assertFalse(registry["eam_send_commissioned"])
        self.assertFalse(registry["production_approved"])

    def test_prod_denied(self):
        with self.assertRaisesRegex(FrameworkError,"HOLD"):
            require_production_authorization("lab-warehouse")

if __name__=="__main__":unittest.main()
