"""Native GitHub dropdown lists come from factory manifests, not manual hardcoding."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reusable_cicd.core import FrameworkError
from scripts import sync_workflow_choices as dropdowns

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ignition-eam-multi-factory.yml"


class ManifestGeneratedChoicesTests(unittest.TestCase):
    def test_factory_and_project_dropdowns_match_registered_manifests(self):
        factories, projects = dropdowns.collect_choices(ROOT / "factories")
        self.assertEqual(set(factories), {"lab-warehouse", "lab-assembly", "lab-packaging"})
        self.assertEqual(set(projects), {
            "FactoryASmoke", "WarehouseHMI", "ConveyorHMI", "PackagingHMI",
            "PackagingLineHMI",
        })
        current = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(
            dropdowns.render(current, factories, projects), current,
            "choice lists drifted from manifests: regenerate before merging"
        )
        self.assertTrue(dropdowns.sync(ROOT, check=True))

    def test_generated_options_expand_without_new_hardcoded_names(self):
        factory_names = ["lab-warehouse", "lab-new"]
        records = {
            "lab-warehouse": {"factory_id": "lab-warehouse",
                              "gateways": [{"projects": [{"name": "WarehouseHMI"}]}]},
            "lab-new": {"factory_id": "lab-new",
                        "gateways": [{"projects": [{"name": "CustomMixerHMI"}]}]},
        }
        with patch.object(dropdowns, "discover_factories", return_value=factory_names), \
             patch.object(dropdowns, "load_factory", side_effect=lambda root, factory: records[factory]):
            factories, projects = dropdowns.collect_choices(ROOT / "factories")
        self.assertIn("lab-new", factories)
        self.assertIn("CustomMixerHMI", projects)
        rendered = dropdowns.render(WORKFLOW.read_text(), factories, projects)
        self.assertIn("          - lab-new\n", rendered)
        self.assertIn("          - CustomMixerHMI\n", rendered)
        self.assertEqual(rendered.count("        type: choice\n"), 2)
        self.assertIn("environment: ignition-test", rendered)

    def test_check_detects_drift_without_mutating_workflow(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / dropdowns.WORKFLOW
            path.parent.mkdir(parents=True)
            workflow = WORKFLOW.read_text().replace(
                "          - PackagingLineHMI\n", "", 1
            )
            self.assertNotEqual(workflow, WORKFLOW.read_text())
            path.write_text(workflow, encoding="utf-8")
            with patch.object(dropdowns, "collect_choices", return_value=(
                *dropdowns.collect_choices(ROOT / "factories"),
            )):
                self.assertFalse(dropdowns.sync(root, check=True))
            self.assertEqual(path.read_text(), workflow, "read-only check modified source")

    def test_generator_refuses_invalid_manifest_choice_injection(self):
        with patch.object(dropdowns, "discover_factories", return_value=["lab-warehouse"]), \
             patch.object(dropdowns, "load_factory", return_value={
                 "factory_id": "lab-warehouse",
                 "gateways": [{"projects": [{"name": "Project\nBAD"}]}],
             }):
            with self.assertRaisesRegex(FrameworkError, "unsafe project"):
                dropdowns.collect_choices(ROOT / "factories")

    def test_large_factory_catalog_fails_instead_of_truncating_dropdown(self):
        factories = ["lab-warehouse"]
        records = {"factory_id": "lab-warehouse", "gateways": [
            {"projects": [{"name": "Project" + str(i)} for i in range(101)]}
        ]}
        with patch.object(dropdowns, "discover_factories", return_value=factories), \
             patch.object(dropdowns, "load_factory", return_value=records):
            with self.assertRaisesRegex(FrameworkError, "too many project"):
                dropdowns.collect_choices(ROOT / "factories")

    def test_ui_cannot_claim_cascading_filtering(self):
        content = WORKFLOW.read_text()
        self.assertIn("Select Project (validated against chosen Factory)", content)
        self.assertEqual(content.count("        type: choice"), 2)
        self.assertNotIn("      action:", content)
        self.assertNotIn("      gateway_id:", content)
        self.assertIn("needs: validate", content)
        self.assertIn("environment: ignition-test", content)


if __name__ == "__main__":
    unittest.main()
