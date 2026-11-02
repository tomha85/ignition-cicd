"""Safety regression for two-input factory + project manual staging workflow."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from reusable_cicd.core import FrameworkError
from framework.deployment.planner import resolve_project_gateway
from scripts.manual_factory_dispatch import APPROVED_STAGE, authorize_stage, select

ROOT=Path(__file__).resolve().parents[1]
SHA="a"*40

class FactoryProjectTests(unittest.TestCase):
    def test_resolve_one_gateway_from_manifest(self):
        examples=(("lab-warehouse","FactoryASmoke","warehouse-main"),
                  ("lab-warehouse","WarehouseHMI","warehouse-main"),
                  ("lab-assembly","ConveyorHMI","assembly-main"),
                  ("lab-packaging","PackagingLineHMI","packaging-main"))
        for factory,project,expected in examples:
            with self.subTest(factory=factory,project=project):
                self.assertEqual(resolve_project_gateway(ROOT,factory,project),expected)
                self.assertEqual(select(factory,None,project,SHA)["gateway_id"],expected)

    def test_ambiguous_project_rejected_not_guessed(self):
        for fn in (lambda:resolve_project_gateway(ROOT,"lab-assembly","PackagingHMI"),
                   lambda:select("lab-assembly",None,"PackagingHMI",SHA)):
            with self.assertRaisesRegex(FrameworkError,"AMBIGUOUS_GATEWAY"):
                fn()

    def test_cross_factory_unknown_and_injected_project_rejected(self):
        for factory,project in (
            ("lab-warehouse","PackagingLineHMI"),
            ("lab-packaging","FactoryASmoke"),
            ("no-such-factory","FactoryASmoke"),
            ("lab-warehouse","../FactoryASmoke"),
        ):
            with self.subTest(factory=factory,project=project):
                with self.assertRaises(FrameworkError):
                    resolve_project_gateway(ROOT,factory,project)

    def test_only_commissioned_source_can_stage(self):
        self.assertEqual(APPROVED_STAGE,("lab-warehouse","warehouse-main","FactoryASmoke"))
        for f,p in (("lab-assembly","ConveyorHMI"),
                    ("lab-packaging","PackagingLineHMI"),
                    ("lab-warehouse","WarehouseHMI")):
            with self.assertRaisesRegex(FrameworkError,"VALIDATE ONLY"):
                authorize_stage(f,resolve_project_gateway(ROOT,f,p),p)

    def test_exactly_two_manual_inputs_and_two_jobs(self):
        text=(ROOT/".github/workflows/ignition-eam-multi-factory.yml").read_text()
        header=text.split("permissions:",1)[0]
        self.assertIn("workflow_dispatch:",header)
        self.assertIn("      factory:",header)
        self.assertIn("      project:",header)
        self.assertIn("options: [FactoryASmoke, WarehouseHMI, ConveyorHMI, PackagingHMI, PackagingLineHMI]",header)
        self.assertNotIn("      action:",header)
        self.assertNotIn("      gateway_id:",header)
        jobs=re.findall(r"^  ([a-z][a-z0-9-]*):$",text.split("jobs:",1)[1],re.M)
        self.assertEqual(jobs,["validate","stage-controller"])
        self.assertIn("needs: validate",text)
        self.assertIn("environment: ignition-test",text)
        self.assertIn("refs/heads/main",text)
        self.assertIn("needs.validate.outputs.stage_eligible == 'true'",text)
        self.assertIn("scripts/verify_stage_approval.py",text)
        self.assertNotIn("eam_multi_factory_deploy.py",text)

    def test_cli_emits_verified_gateway_and_stage_eligibility(self):
        cases=(("lab-warehouse","FactoryASmoke","warehouse-main","true"),
               ("lab-assembly","ConveyorHMI","assembly-main","false"),
               ("lab-packaging","PackagingLineHMI","packaging-main","false"))
        with tempfile.TemporaryDirectory() as temp:
            for factory,project,gw,eligible in cases:
                out=Path(temp)/(factory+".txt")
                cp=subprocess.run(
                    [sys.executable,"scripts/manual_factory_dispatch.py",
                     "--action","validate","--factory",factory,
                     "--project",project,"--sha",SHA,"--github-output",str(out)],
                    cwd=ROOT,text=True,capture_output=True,timeout=30)
                self.assertEqual(cp.returncode,0,cp.stderr)
                values=dict(x.split("=",1) for x in out.read_text().splitlines())
                self.assertEqual(values,{"gateway_id":gw,"stage_eligible":eligible})

    def test_cli_ambiguous_mapping_cannot_emit_gateway(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/"blocked"
            cp=subprocess.run(
                [sys.executable,"scripts/manual_factory_dispatch.py",
                 "--action","validate","--factory","lab-assembly",
                 "--project","PackagingHMI","--sha",SHA,"--github-output",str(output)],
                cwd=ROOT,text=True,capture_output=True,timeout=30)
            self.assertNotEqual(cp.returncode,0)
            self.assertIn("AMBIGUOUS_GATEWAY",cp.stderr)
            self.assertFalse(output.exists())

if __name__=="__main__":
    unittest.main()
