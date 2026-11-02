"""Read-only EAM OpenAPI diagnostics must not invoke mutation routes."""
import pathlib
import unittest
from scripts import eam_openapi_diagnostics

class DiagnosticsSafetyTests(unittest.TestCase):
    def test_no_http_write_methods(self):
        data=pathlib.Path(eam_openapi_diagnostics.__file__).read_text()
        self.assertNotIn('method="POST"',data)
        self.assertNotIn('method="DELETE"',data)
        self.assertNotIn('method="PUT"',data)
        self.assertNotIn('docker", "cp"',data)

    def test_container_names_fixed(self):
        self.assertEqual(eam_openapi_diagnostics.CONTROLLER,"ignition-eam-controller")
        self.assertEqual(eam_openapi_diagnostics.AGENT,"ignition-eam-agent")

if __name__=="__main__":
    unittest.main()
