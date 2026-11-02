"""Tests for provenance without changing Git-tracked project files."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.eam_stamp_project_description import stamp


class TestEamProjectDescription(unittest.TestCase):
    def test_stamp_is_staging_only_and_content_hash_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "project.json").write_text(json.dumps({
                "title": "WarehouseHMI", "description": "Isolated TEST-only", "enabled": True
            }))
            (base / "view.json").write_text('{"root":{}}')
            sha = "a" * 40
            first = stamp(base, "factory_a", sha, "123456")
            desc = json.loads((base / "project.json").read_text())["description"]
            self.assertIn("EAM TEST STAGED", desc)
            self.assertIn("source=aaaaaaaaaaaa", desc)
            self.assertIn("NOT AGENT VERIFIED", desc)
            second = stamp(base, "factory_a", "b" * 40, "123457")
            self.assertEqual(first["source_content_sha256"], second["source_content_sha256"])
            self.assertNotEqual(first["release_sha"], second["release_sha"])

    def test_invalid_release_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "project.json").write_text('{"title":"WarehouseHMI"}')
            with self.assertRaises(ValueError):
                stamp(base, "factory_a", "invalid", "123")


if __name__ == "__main__":
    unittest.main()
