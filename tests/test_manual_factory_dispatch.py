"""New manual-selector tests. Only read-only validation; no Gateway calls."""
import subprocess
import sys
import unittest
from pathlib import Path
from reusable_cicd.core import FrameworkError
from scripts.manual_factory_dispatch import select, authorize_stage

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40

class ManualFactoryDispatchTests(unittest.TestCase):
    def test_factory_a_select(self):
        plan = select("lab-warehouse", "warehouse-main", "FactoryASmoke", SHA)
        self.assertEqual(plan["status"], "VALIDATED_NOT_DEPLOYED")
        self.assertFalse(plan["deployment_authorized"])
        self.assertEqual(plan["eam_send_project"], "NOT_RUN")

    def test_factory_b_select(self):
        plan = select("lab-assembly", "assembly-main", "ConveyorHMI", SHA)
        self.assertEqual(plan["project"], "ConveyorHMI")
        self.assertEqual(plan["browser_render"], "NOT_TESTED")

    def test_factory_b_second_gateway(self):
        plan = select("lab-assembly", "utilities-main", "PackagingHMI", SHA)
        self.assertEqual(plan["gateway_id"], "utilities-main")

    def test_wrong_factory_project_rejected(self):
        with self.assertRaises(FrameworkError):
            select("lab-assembly", "utilities-main", "ConveyorHMI", SHA)

    def test_unknown_factory_rejected(self):
        with self.assertRaises(FrameworkError):
            select("missing-customer", "warehouse-main", "FactoryASmoke", SHA)

    def test_injection_rejected(self):
        with self.assertRaisesRegex(FrameworkError, "invalid project"):
            select("lab-warehouse", "warehouse-main", 'FactoryASmoke"; echo BAD', SHA)

    def test_stage_allowlist(self):
        authorize_stage("lab-warehouse", "warehouse-main", "FactoryASmoke")
        for args in (("lab-warehouse","warehouse-main","WarehouseHMI"),
                     ("lab-assembly","assembly-main","ConveyorHMI"),
                     ("lab-assembly","utilities-main","PackagingHMI")):
            with self.subTest(args=args), self.assertRaisesRegex(FrameworkError,"VALIDATE ONLY"):
                authorize_stage(*args)

    def test_manual_cli_validate(self):
        for fac,gw,project in (
            ("lab-warehouse","warehouse-main","FactoryASmoke"),
            ("lab-assembly","assembly-main","ConveyorHMI"),
            ("lab-assembly","utilities-main","PackagingHMI")
        ):
            proc = subprocess.run([sys.executable,"scripts/manual_factory_dispatch.py",
                "--action","validate","--factory",fac,"--gateway",gw,
                "--project",project,"--sha",SHA],
                cwd=ROOT,text=True,capture_output=True,timeout=15)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn("VALIDATED_NOT_DEPLOYED",proc.stdout)

if __name__ == "__main__":
    unittest.main()
