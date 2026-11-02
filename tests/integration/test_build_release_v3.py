"""Source package contains real native Ignition resources and a pinned release SHA."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from reusable_cicd.core import FrameworkError
from scripts.build_release_v3 import build

ROOT=Path(__file__).resolve().parents[2]
SHA="a"*40

class ReleaseBuildTest(unittest.TestCase):
    def test_package_matches_source(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/"FactoryASmoke.zip"
            result=build(ROOT,"lab-warehouse","warehouse-main","FactoryASmoke",SHA,output)
            self.assertEqual(result["status"],"BUILT_NOT_DEPLOYED")
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as z:
                manifest=json.loads(z.read("release-manifest.json"))
                self.assertEqual(manifest["git_sha"],SHA)
                self.assertFalse(manifest["production_approved"])
                self.assertEqual(manifest["eam_agent_task"],"NOT_RUN")
                for rel,digest in manifest["source_hashes"].items():
                    self.assertEqual(hashlib.sha256(z.read("FactoryASmoke/"+rel)).hexdigest(),digest)

    def test_cannot_overwrite_existing_release(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"existing.zip"
            path.write_bytes(b"already exists")
            with self.assertRaisesRegex(FrameworkError,"no overwrite"):
                build(ROOT,"lab-warehouse","warehouse-main","FactoryASmoke",SHA,path)

    def test_wrong_project_fails(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(FrameworkError,"not assigned"):
                build(ROOT,"lab-assembly","utilities-main","ConveyorHMI",SHA,Path(t)/"fail.zip")

if __name__=="__main__":unittest.main()
