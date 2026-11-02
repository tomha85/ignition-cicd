"""Validates three distinct factory examples without contacting any Gateway."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from reusable_cicd.core import FrameworkError, load_factory, validate_catalog
from scripts.build_release_v3 import build
from scripts.manual_factory_dispatch import authorize_stage, select

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/"factories"
SHA="a"*40

class ThreeFactoryExamples(unittest.TestCase):
    def test_factory_roster_and_gateway_scales(self):
        self.assertEqual(validate_catalog(CATALOG),
                         ["lab-assembly","lab-packaging","lab-warehouse"])
        self.assertEqual(len(load_factory(CATALOG,"lab-warehouse")["gateways"]),1)
        self.assertEqual(len(load_factory(CATALOG,"lab-assembly")["gateways"]),2)
        self.assertEqual(len(load_factory(CATALOG,"lab-packaging")["gateways"]),1)

    def test_all_three_build_real_native_ignition_archives(self):
        samples=(("lab-warehouse","warehouse-main","FactoryASmoke"),
                 ("lab-assembly","assembly-main","ConveyorHMI"),
                 ("lab-packaging","packaging-main","PackagingLineHMI"))
        with tempfile.TemporaryDirectory() as tmp:
            for factory,gateway,project in samples:
                package=Path(tmp)/(factory+".zip")
                result=build(ROOT,factory,gateway,project,SHA,package)
                self.assertEqual(result["status"],"BUILT_NOT_DEPLOYED")
                self.assertFalse(result["production_approved"])
                with zipfile.ZipFile(package) as archive:
                    self.assertIn(project+"/project.json",archive.namelist())
                    self.assertIn(project+"/com.inductiveautomation.perspective/views/Main/view.json",archive.namelist())
                    for rel,hashval in result["source_hashes"].items():
                        self.assertEqual(hashlib.sha256(archive.read(project+"/"+rel)).hexdigest(),hashval)

    def test_packaging_source_only_stage_denied(self):
        result=select("lab-packaging","packaging-main","PackagingLineHMI",SHA)
        self.assertEqual(result["status"],"VALIDATED_NOT_DEPLOYED")
        self.assertFalse(result["deployment_authorized"])
        self.assertEqual(result["eam_send_project"],"NOT_RUN")
        with self.assertRaisesRegex(FrameworkError,"VALIDATE ONLY"):
            authorize_stage("lab-packaging","packaging-main","PackagingLineHMI")

    def test_factory_source_isolation_rejects_wrong_project(self):
        with self.assertRaises(FrameworkError):
            select("lab-warehouse","warehouse-main","PackagingLineHMI",SHA)
        with self.assertRaises(FrameworkError):
            select("lab-packaging","packaging-main","WarehouseHMI",SHA)

    def test_packaging_view_clearly_identifies_synthetic_data(self):
        path=CATALOG/"lab-packaging/projects/PackagingLineHMI/com.inductiveautomation.perspective/views/Main/view.json"
        view=json.loads(path.read_text())
        labels=[element["props"]["text"] for element in view["root"]["children"]]
        self.assertTrue(any("NO PLC" in x for x in labels))
        self.assertFalse(load_factory(CATALOG,"lab-packaging")["gateways"][0]["environments"]["test"]["deployment_enabled"])
