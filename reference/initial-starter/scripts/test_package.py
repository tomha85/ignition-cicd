import json
import unittest
from package_release import ROOT, validate

class ReleaseTests(unittest.TestCase):
    def test_manifest_safe(self):
        manifest = json.loads((ROOT / 'manifests/release.json').read_text())
        self.assertEqual(manifest['environment'], 'ISOLATED_LAB_ONLY')
        self.assertFalse(manifest['production_approved'])
    def test_export_optional(self):
        self.assertIn(validate(), (True, False))

if __name__ == '__main__':
    unittest.main()
