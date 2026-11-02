"""Safety and reuse tests independent from a live Ignition Gateway."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import (FrameworkError, discover_factories,
                                load_factory, plan_release, validate_catalog)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "factories"
SHA = "a" * 40


class ReusableFrameworkTests(unittest.TestCase):
    def test_real_catalog_is_discovered_and_valid(self):
        self.assertEqual(validate_catalog(CATALOG), ["lab-assembly", "lab-warehouse"])

    def test_no_factory_hardcoded_into_engine(self):
        self.assertNotIn("factory_a", (ROOT / "reusable_cicd/core.py").read_text())
        self.assertNotIn("WarehouseHMI", (ROOT / "reusable_cicd/core.py").read_text())

    def test_small_and_complex_releases(self):
        a = plan_release(CATALOG, "lab-warehouse", "warehouse-main", "test", SHA)
        b = plan_release(CATALOG, "lab-assembly", "assembly-main", "test", SHA)
        self.assertEqual({p["name"] for p in a["projects"]}, {"WarehouseHMI", "FactoryASmoke"})
        self.assertEqual(len(b["projects"]), 2)
        self.assertEqual(a["status"], "VALIDATED_NOT_DEPLOYED")
        self.assertEqual(b["fat"], "NOT_TESTED")
        self.assertFalse(b["deployment_authorized"])
        self.assertTrue(all(p["file_count"] >= 2 for p in b["projects"]))

    def test_production_plan_never_claims_approval(self):
        p = plan_release(CATALOG, "lab-warehouse", "warehouse-main", "production", SHA)
        self.assertFalse(p["production_approved"])
        self.assertFalse(p["deployment_authorized"])

    def test_multi_gateway_manifest(self):
        config = load_factory(CATALOG, "lab-assembly")
        self.assertEqual(len(config["gateways"]), 2)

    def test_cli_is_read_only(self):
        proc = subprocess.run(
            [sys.executable, "scripts/reusable_factory.py", "--check-catalog"],
            cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VALIDATED_NOT_DEPLOYED", proc.stdout)

    def test_invalid_sha_rejected(self):
        with self.assertRaises(FrameworkError):
            plan_release(CATALOG, "lab-warehouse", "warehouse-main", "test", "short")

    def test_invalid_factory_path_rejected(self):
        with self.assertRaises(FrameworkError):
            load_factory(CATALOG, "../lab-warehouse")

    def test_missing_gateway_rejected(self):
        with self.assertRaises(FrameworkError):
            plan_release(CATALOG, "lab-warehouse", "not-registered", "test", SHA)

    def test_catalog_has_no_embedded_secret_values(self):
        for manifest in CATALOG.glob("*/factory.json"):
            data = manifest.read_text()
            self.assertNotIn("api_token:", data.lower())
            self.assertNotIn("password:", data.lower())

    def test_cross_factory_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for fid in ("one", "two"):
                src = CATALOG / "lab-warehouse"
                import shutil
                shutil.copytree(src, root / fid)
                manifest = json.loads((root / fid / "factory.json").read_text())
                manifest["factory_id"] = fid
                (root / fid / "factory.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(FrameworkError, "collision"):
                validate_catalog(root)

    def test_factory_reuse_without_engine_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "new-customer"
            shutil.copytree(CATALOG / "lab-warehouse", target)
            manifest = json.loads((target / "factory.json").read_text())
            manifest["factory_id"] = "new-customer"
            manifest["gateways"][0]["gateway_id"] = "new-gateway"
            manifest["gateways"][0]["environments"]["test"]["github_environment"] = "new-customer-test"
            manifest["gateways"][0]["environments"]["test"]["target_id"] = "new-test-agent"
            (target / "factory.json").write_text(json.dumps(manifest))
            self.assertEqual(discover_factories(Path(tmp)), ["new-customer"])
            plan = plan_release(Path(tmp), "new-customer", "new-gateway", "test", SHA)
            self.assertEqual(plan["factory_id"], "new-customer")

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "lab-warehouse"
            shutil.copytree(CATALOG / "lab-warehouse", target)
            manifest = json.loads((target / "factory.json").read_text())
            manifest["gateways"][0]["projects"][0]["source"] = "projects/../../outside"
            (target / "factory.json").write_text(json.dumps(manifest))
            with self.assertRaises(FrameworkError):
                load_factory(Path(tmp), "lab-warehouse")

    def test_symlink_resource_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "lab-warehouse"
            shutil.copytree(CATALOG / "lab-warehouse", target)
            project = target / "projects/WarehouseHMI"
            (project / "unsafe-link").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(FrameworkError, "symlink"):
                load_factory(Path(tmp), "lab-warehouse")

    def test_unknown_secret_name_cannot_be_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "lab-warehouse"
            shutil.copytree(CATALOG / "lab-warehouse", target)
            data = json.loads((target / "factory.json").read_text())
            data["gateways"][0]["environments"]["test"]["secret_refs"] = ["token=plaintext"]
            (target / "factory.json").write_text(json.dumps(data))
            with self.assertRaises(FrameworkError):
                load_factory(Path(tmp), "lab-warehouse")

    def test_deploy_opt_in_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "lab-warehouse"
            shutil.copytree(CATALOG / "lab-warehouse", target)
            data = json.loads((target / "factory.json").read_text())
            data["gateways"][0]["environments"]["test"]["deployment_enabled"] = True
            (target / "factory.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(FrameworkError, "deployment_enabled"):
                load_factory(Path(tmp), "lab-warehouse")


if __name__ == "__main__":
    unittest.main()
