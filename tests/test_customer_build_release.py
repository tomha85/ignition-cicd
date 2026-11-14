"""Offline customer ZIP packaging from exact config selections (no EAM writes)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import load_profile
from scripts.customer_build_release import make_releases

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config/example-company-multi-site.json"
SHA = "b" * 40


class CustomerNativeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(PROFILE)

    def test_one_engine_packages_local_workshops_and_remote_factories(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "releases"
            report = make_releases(ROOT, self.profile, SHA, dest)
            self.assertEqual(report["status"],
                             "CUSTOMER_NATIVE_RELEASES_BUILT_NOT_DEPLOYED")
            self.assertEqual(report["release_count"], 4)
            self.assertEqual(report["runtime_fat"], "NOT_TESTED")
            self.assertEqual(report["production"], "HOLD")
            sites = {x["site_id"] for x in report["releases"]}
            self.assertEqual(len(sites), 3)
            for record in report["releases"]:
                self.assertFalse(record["production_approved"])
                self.assertEqual(record["eam_send_project"], "NOT_RUN")
                archive = dest / record["archive"]
                self.assertTrue(archive.is_file())
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                                 record["archive_sha256"])
                with zipfile.ZipFile(archive) as bundle:
                    self.assertIn("release-manifest.json", bundle.namelist())
                    manifest = json.loads(bundle.read("release-manifest.json"))
                    self.assertEqual(manifest["git_sha"], SHA)
                    self.assertEqual(manifest["project"], record["project"])
                    self.assertEqual(manifest["source_hashes"],
                                     record["native_source_hashes"])
                    self.assertEqual(manifest["status"], "BUILT_NOT_DEPLOYED")

    def test_can_build_exact_same_site_workshop(self):
        with tempfile.TemporaryDirectory() as temp:
            report = make_releases(
                ROOT, self.profile, SHA, Path(temp),
                factory="lab-assembly", gateway="utilities-main",
                project="PackagingHMI")
            self.assertEqual(report["release_count"], 1)
            self.assertEqual(report["releases"][0]["workshop_id"], "utilities-shop")

    def test_unknown_target_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "out"
            with self.assertRaises(FrameworkError):
                make_releases(ROOT, self.profile, SHA, target,
                              factory="unknown-plant")
            self.assertFalse(target.exists())

    def test_invalid_git_sha_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FrameworkError):
                make_releases(ROOT, self.profile, "short", Path(temp))

    def test_no_overwrite_existing_release(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            make_releases(ROOT, self.profile, SHA, dest,
                          factory="lab-packaging")
            with self.assertRaisesRegex(FrameworkError, "already exists"):
                make_releases(ROOT, self.profile, SHA, dest,
                              factory="lab-packaging")


if __name__ == "__main__":
    unittest.main()
