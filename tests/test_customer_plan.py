"""Customer-configured multi-factory plans are read-only and fork-safe."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import build_plan, load_profile

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "config/example-customer-testlab.json"
SHA = "a" * 40


class CustomerPlanTests(unittest.TestCase):
    def setUp(self):
        self.demo = load_profile(DEMO)

    def test_three_factory_demo_builds_four_independent_plans(self):
        result = build_plan(ROOT, self.demo, SHA)
        self.assertEqual(result["factory_count"], 3)
        self.assertEqual(result["target_count"], 4)
        self.assertEqual(result["status"], "VALIDATED_NOT_DEPLOYED")
        self.assertEqual(result["production"], "HOLD")
        for site in result["targets"]:
            self.assertTrue(site["source_sha256"])
            self.assertFalse(site["deployment_authorized"])
            self.assertEqual(site["eam_send_project"], "NOT_RUN")
            self.assertEqual(site["browser_fat"], "NOT_TESTED")

    def test_filter_factory_gateway_project_including_ambiguous_name(self):
        result = build_plan(ROOT, self.demo, SHA, factory="lab-assembly",
                            gateway="utilities-main", project="PackagingHMI")
        self.assertEqual(result["target_count"], 1)
        self.assertEqual(result["targets"][0]["gateway_id"], "utilities-main")

    def test_wrong_selection_fails_closed(self):
        with self.assertRaisesRegex(FrameworkError, "no configured target matched"):
            build_plan(ROOT, self.demo, SHA, factory="missing-factory")

    def test_invalid_git_sha_fails_closed(self):
        with self.assertRaises(FrameworkError):
            build_plan(ROOT, self.demo, "abc")

    def test_private_credentials_never_exposed_in_result(self):
        result = build_plan(ROOT, self.demo, SHA)
        report = json.dumps(result)
        self.assertNotIn("IGNITION_GATEWAY_API_TOKEN", report)
        self.assertNotIn("eam-controller.example.invalid", report)

    def test_forbidden_inline_secret_and_unreviewed_mode(self):
        for edit in ("token", "password", "private_key"):
            with self.subTest(edit=edit):
                example = copy.deepcopy(self.demo)
                example["targets"][0]["eam"][edit] = "leaked-value"
                self.assert_invalid_config(example)
        example = copy.deepcopy(self.demo)
        example["mode"] = "deploy"
        self.assert_invalid_config(example)

    def test_insecure_or_unparseable_controller_url_rejected(self):
        for url in (
            "http://localhost:8088",
            "https://user:password@example.com:8043",
            "https://host.example.invalid:99999",
            "https://host.example.invalid:8043/project?token=secret",
            "https://host.example.invalid",
        ):
            with self.subTest(url=url):
                example = copy.deepcopy(self.demo)
                example["targets"][0]["eam"]["controller_url"] = url
                self.assert_invalid_config(example)

    def test_duplicate_target_rejected(self):
        example = copy.deepcopy(self.demo)
        example["targets"].append(copy.deepcopy(example["targets"][0]))
        self.assert_invalid_config(example)

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaises(FrameworkError):
                load_profile(path)

    def test_new_customer_names_require_no_python_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory_dir = root / "factories" / "custom-water-plant"
            project_dir = factory_dir / "projects" / "PumpHMI"
            view = project_dir / "com.inductiveautomation.perspective" / "views" / "Main"
            view.mkdir(parents=True)
            (project_dir / "project.json").write_text(
                json.dumps({"title": "PumpHMI"}), encoding="utf-8")
            (view / "resource.json").write_text(
                json.dumps({"files": ["view.json"]}), encoding="utf-8")
            (view / "view.json").write_text("{}", encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "factory_id": "custom-water-plant",
                "ignition_version": "8.3",
                "gateways": [{
                    "gateway_id": "west-gateway",
                    "projects": [{"name": "PumpHMI", "source": "projects/PumpHMI"}],
                    "environments": {"test": {
                        "github_environment": "custom-water-test",
                        "deployment_method": "eam",
                        "target_id": "west-test",
                        "secret_refs": ["EAM_API_TOKEN"],
                        "deployment_enabled": False,
                    }},
                }],
            }
            (factory_dir / "factory.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            profile = copy.deepcopy(self.demo)
            profile["customer_id"] = "custom-water-company"
            profile["targets"] = [copy.deepcopy(profile["targets"][0])]
            profile["targets"][0].update(
                factory_id="custom-water-plant",
                gateway_id="west-gateway",
                project="PumpHMI")
            plan = build_plan(root, profile, SHA)
            self.assertEqual(plan["target_count"], 1)
            self.assertEqual(plan["targets"][0]["project"], "PumpHMI")
            self.assertEqual(plan["targets"][0]["source_files"], 3)

    def assert_invalid_config(self, config):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "customer.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(FrameworkError):
                load_profile(path)


if __name__ == "__main__":
    unittest.main()
