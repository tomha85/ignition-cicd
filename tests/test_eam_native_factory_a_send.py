"""Native EAM Smoke contract checks, no live REST changes in unit tests."""
import unittest
from scripts import eam_native_factory_a_send as m

class NativeEamSmokeSafetyTests(unittest.TestCase):
    def test_fixed_allowed_target(self):
        self.assertEqual((m.CONTROLLER,m.AGENT,m.PROJECT),(
            "ignition-eam-controller","ignition-eam-agent","FactoryASmoke"))
        self.assertEqual(m.TASK,"CICD-SEND-FactoryASmoke-A")
    def test_match_correct_agent(self):
        self.assertTrue(m.match_approved_agent({"items":[{"name":"EAM-Agent","id":"agent-123"}]},"agent-123"))
        self.assertFalse(m.match_approved_agent({"items":[{"name":"Different","id":"agent-123"}]},"agent-123"))
        self.assertFalse(m.match_approved_agent({"items":[{"name":"EAM-Agent","id":"agent-456"}]},"agent-123"))
    def test_no_unqualified_production_path(self):
        self.assertNotIn("production",m.FACTORY)
if __name__=="__main__":
    unittest.main()
