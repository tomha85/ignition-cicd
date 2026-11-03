"""Generic EAM planner accepts multiple configurations but cannot deploy."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from framework.deployment.generic_eam import resolve
from reusable_cicd.core import FrameworkError

ROOT = Path(__file__).resolve().parents[1]

class GenericEamCandidateTests(unittest.TestCase):
    def test_existing_warehouse_resolves_without_mutation(self):
        path = ROOT / "generic-eam/targets.json"
        before = path.read_bytes()
        plan = resolve(ROOT, "lab-warehouse", "WarehouseHMI")
        self.assertEqual(plan["controller_id"], "ignition-eam-controller")
        self.assertEqual(plan["eam_task"], "CICD-SEND-WarehouseHMI-A")
        self.assertEqual(plan["runner_labels"], ["self-hosted", "linux", "ignition-lab"])
        self.assertEqual(plan["status"], "CONFIG_RESOLVED_NOT_DEPLOYED")
        self.assertFalse(plan["deployment_authorized"])
        self.assertFalse(plan["production_approved"])
        self.assertEqual(before, path.read_bytes())

    def fixture(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        shutil.copytree(ROOT / "factories", root / "factories")
        (root / "generic-eam").mkdir()
        original = json.loads((ROOT / "generic-eam/targets.json").read_text())
        return tmp, root, original

    def save(self, root, data):
        (root / "generic-eam/targets.json").write_text(json.dumps(data))

    def test_second_factory_dynamic_without_engine_edit(self):
        tmp, root, data = self.fixture()
        try:
            new = copy.deepcopy(data["targets"][0])
            new.update(target_id="lab-packaging-test-agent", factory_id="lab-packaging",
                       gateway_id="packaging-main", runner_labels=["self-hosted","linux","plant-packaging"],
                       approval_environment="ignition-test-packaging")
            new["controller"] = {"id":"packaging-controller",
                                 "api_base_url":"https://gateway.example.invalid:8043",
                                 "secret_ref":"PACKAGING_EAM_TOKEN",
                                 "ca_ref":"PACKAGING_CA_FILE"}
            new["agent"] = {"id":"packaging-agent", "eam_agent_name":"PackagingAgent"}
            new["tasks"] = [{"project":"PackagingLineHMI",
                             "task_name":"PACKAGING-SEND",
                             "agent_name":"PackagingAgent"}]
            data["targets"].append(new)
            self.save(root, data)
            plan = resolve(root, "lab-packaging", "PackagingLineHMI")
            self.assertEqual(plan["runner_labels"][-1], "plant-packaging")
            self.assertEqual(plan["eam_task"], "PACKAGING-SEND")
            self.assertEqual(plan["controller_api_base_url"], "https://gateway.example.invalid:8043")
            self.assertFalse(plan["deployment_authorized"])
        finally:
            tmp.cleanup()

    def test_wrong_factory_project_rejected(self):
        with self.assertRaises(FrameworkError):
            resolve(ROOT, "lab-assembly", "WarehouseHMI")

    def test_ambiguous_mapping_rejected(self):
        with self.assertRaisesRegex(FrameworkError, "AMBIGUOUS_GATEWAY"):
            resolve(ROOT, "lab-assembly", "PackagingHMI")

    def test_no_task_does_not_guess(self):
        with self.assertRaisesRegex(FrameworkError, "no unique reviewed EAM task"):
            resolve(ROOT, "lab-warehouse", "FactoryASmoke")

    def test_production_forbidden(self):
        with self.assertRaisesRegex(FrameworkError, "production"):
            resolve(ROOT, "lab-warehouse", "WarehouseHMI", "production")

    def test_wrong_gateway_rejected(self):
        with self.assertRaisesRegex(FrameworkError, "explicit gateway"):
            resolve(ROOT, "lab-warehouse", "WarehouseHMI", gateway="assembly-main")

    def test_duplicate_target_rejected(self):
        tmp, root, data = self.fixture()
        try:
            data["targets"].append(copy.deepcopy(data["targets"][0]))
            self.save(root, data)
            with self.assertRaisesRegex(FrameworkError, "duplicate"):
                resolve(root, "lab-warehouse", "WarehouseHMI")
        finally:
            tmp.cleanup()

    def test_inline_secret_or_untrusted_endpoint_rejected(self):
        for field, value in (("api_base_url","http://insecure.invalid:8043"),
                             ("api_base_url","https://user:pass@server.invalid:8043"),
                             ("secret_ref","my_password")):
            with self.subTest(field=field, value=value):
                tmp, root, data = self.fixture()
                try:
                    data["targets"][0]["controller"][field] = value
                    self.save(root, data)
                    with self.assertRaises(FrameworkError):
                        resolve(root, "lab-warehouse", "WarehouseHMI")
                finally:
                    tmp.cleanup()

    def test_no_runner_or_unreviewed_deployment(self):
        for field, value in (("runner_labels", ["ubuntu-latest"]),
                             ("deployment_enabled", True)):
            with self.subTest(field=field):
                tmp, root, data = self.fixture()
                try:
                    data["targets"][0][field] = value
                    self.save(root, data)
                    with self.assertRaises(FrameworkError):
                        resolve(root, "lab-warehouse", "WarehouseHMI")
                finally:
                    tmp.cleanup()

if __name__ == "__main__":
    unittest.main()
