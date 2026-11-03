"""TEST-only description stamping must preserve approved source and hashes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.stage_selected_test_controller import prepare_stamped_copy


class StageDescriptionTests(unittest.TestCase):
    def test_stamped_copy_has_new_description_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "WarehouseHMI"
            source.mkdir()
            (source / "project.json").write_text(
                json.dumps({"title": "WarehouseHMI", "description": "Warehouse TEST"}),
                encoding="utf-8")
            (source / "view.json").write_text('{"text":"HELLO TOMHA"}', encoding="utf-8")
            (root / "stage").mkdir()
            before = {f.name: f.read_bytes() for f in source.iterdir()}
            manifest = {name: hashlib.sha256(data).hexdigest()
                        for name, data in before.items()}
            expected, info = prepare_stamped_copy(
                source, manifest, root / "stage" / "WarehouseHMI",
                "lab-warehouse", "a" * 40, "12345")
            # A pre-existing parent directory is required for staging.
            self.assertEqual({f.name: f.read_bytes() for f in source.iterdir()}, before)
            self.assertEqual(expected["view.json"], manifest["view.json"])
            self.assertNotEqual(expected["project.json"], manifest["project.json"])
            staged = root / "stage" / "WarehouseHMI"
            data = json.loads((staged / "project.json").read_text())
            self.assertIn("EAM TEST STAGED", data["description"])
            self.assertIn("factory=lab-warehouse", data["description"])
            self.assertIn("run=12345", data["description"])
            self.assertIn("NOT AGENT VERIFIED", data["description"])
            self.assertEqual(info["agent_verification"], "NOT_RUN")

    def test_fails_closed_on_mismatched_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "WarehouseHMI"
            src.mkdir()
            (root / "stage").mkdir()
            (src / "project.json").write_text('{"title":"WarehouseHMI"}')
            with self.assertRaisesRegex(FrameworkError, "source hash mismatch"):
                prepare_stamped_copy(src, {"project.json": "0" * 64},
                    root / "stage" / "WarehouseHMI", "lab-warehouse", "a" * 40, "12")

    def test_rejects_invalid_run_before_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "WarehouseHMI"
            src.mkdir()
            (root / "stage").mkdir()
            content = b'{"title":"WarehouseHMI"}'
            (src / "project.json").write_bytes(content)
            with self.assertRaisesRegex(FrameworkError, "run ID"):
                prepare_stamped_copy(src, {"project.json": hashlib.sha256(content).hexdigest()},
                    root / "stage" / "WarehouseHMI", "lab-warehouse", "a" * 40, "")
            self.assertFalse((root / "stage" / "WarehouseHMI").exists())


if __name__ == "__main__":
    unittest.main()
