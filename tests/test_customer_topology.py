"""Portable site/workshop/on-prem/private-cloud EAM config qualification tests.

No connectivity, PLC or remote deployment is allowed. Customer IDs, sites,
workshops and controller endpoints are test inputs, not engine hardcoding.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import build_plan, load_profile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/example-company-multi-site.json"
SHA = "a" * 40


class PortableCustomerTopologyTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(CONFIG)

    def check_rejected(self, config):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "profile.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(FrameworkError):
                load_profile(path)

    def test_same_company_three_sites_and_four_workshops(self):
        plan = build_plan(ROOT, self.profile, SHA)
        self.assertEqual(plan["schema_version"], 2)
        self.assertEqual(plan["customer_id"], "example-multi-site-company")
        self.assertEqual(plan["factory_count"], 3)
        self.assertEqual(plan["site_count"], 3)
        self.assertEqual(plan["workshop_count"], 4)
        self.assertEqual(plan["controller_count"], 2)
        self.assertEqual(plan["target_count"], 4)
        self.assertEqual(plan["status"], "VALIDATED_NOT_DEPLOYED")
        self.assertEqual(plan["production"], "HOLD")
        for target in plan["targets"]:
            self.assertTrue(target["source_sha256"])
            self.assertEqual(target["stage"], "NOT_RUN")
            self.assertEqual(target["eam_send_project"], "NOT_RUN")
            self.assertEqual(target["network_access"], "NOT_VERIFIED")
            self.assertFalse(target["deployment_authorized"])

    def test_same_location_different_workshops_and_gateways(self):
        plan = build_plan(ROOT, self.profile, SHA, factory="lab-assembly")
        self.assertEqual(plan["site_count"], 1)
        self.assertEqual(plan["workshop_count"], 2)
        self.assertEqual(plan["controller_count"], 1)
        self.assertEqual({x["gateway_id"] for x in plan["targets"]},
                         {"assembly-main", "utilities-main"})

    def test_cloud_and_onprem_remain_logical_not_live(self):
        plan = build_plan(ROOT, self.profile, SHA)
        self.assertEqual({p["controller_hosting"] for p in plan["targets"]},
                         {"on_prem", "private_cloud"})
        self.assertEqual({p["transport"] for p in plan["targets"]},
                         {"site_lan", "private_overlay"})
        output = json.dumps(plan)
        self.assertNotIn("eam.private.example.invalid", output)
        self.assertNotIn("HQ_EAM_API_TOKEN", output)
        self.assertNotIn("CLOUD_EAM_API_TOKEN", output)
        self.assertNotIn("HQ_EAM_CA_FILE", output)

    def test_select_exact_factory_gateway_project(self):
        plan = build_plan(ROOT, self.profile, SHA,
                          factory="lab-assembly", gateway="utilities-main",
                          project="PackagingHMI")
        self.assertEqual(plan["target_count"], 1)
        item = plan["targets"][0]
        self.assertEqual((item["site_id"], item["workshop_id"]),
                         ("headquarters-campus", "utilities-shop"))
        self.assertEqual(item["eam_task_name"], "SEND-PackagingHMI-EXAMPLE")

    def test_wrong_site_workshop_fails_closed(self):
        for key, value in (("site_id", "unknown-location"),
                           ("workshop_id", "wrong-workshop"),
                           ("controller_id", "unregistered-eam"),
                           ("project", "Not-Registered")):
            with self.subTest(key=key):
                p = copy.deepcopy(self.profile)
                p["targets"][0][key] = value
                if key == "project":
                    with self.assertRaises(FrameworkError):
                        build_plan(ROOT, p, SHA)
                else:
                    self.check_rejected(p)

    def test_no_inline_passwords_or_unknown_fields(self):
        for key in ("password", "token", "private_key", "ssh_key"):
            with self.subTest(key=key):
                p = copy.deepcopy(self.profile)
                p["controllers"][0][key] = "SHOULD_NOT_BE_HERE"
                self.check_rejected(p)

    def test_secure_controller_url_required(self):
        for value in (
            "http://eam.example.invalid:8088",
            "https://user:password@eam.example.invalid:8043",
            "https://eam.example.invalid",
            "https://eam.example.invalid:99999",
            "https://eam.example.invalid:8043/path",
            "https://eam.example.invalid:8043/?x=y",
        ):
            with self.subTest(value=value):
                p = copy.deepcopy(self.profile)
                p["controllers"][0]["controller_url"] = value
                self.check_rejected(p)

    def test_unknown_network_and_hosting_fail_closed(self):
        for field, value in (
            ("hosting", "public_internet"),
            ("network", "public_internet"),
            ("network", "http"),
        ):
            with self.subTest(field=field):
                p = copy.deepcopy(self.profile)
                p["controllers"][0][field] = value
                self.check_rejected(p)

    def test_duplicate_site_id_or_workshop_rejected(self):
        p = copy.deepcopy(self.profile)
        p["sites"].append(copy.deepcopy(p["sites"][0]))
        self.check_rejected(p)
        p = copy.deepcopy(self.profile)
        p["sites"][0]["workshops"].append("assembly-shop")
        self.check_rejected(p)

    def test_duplicate_project_or_task_binding_rejected(self):
        p = copy.deepcopy(self.profile)
        p["targets"].append(copy.deepcopy(p["targets"][0]))
        self.check_rejected(p)
        p = copy.deepcopy(self.profile)
        p["targets"][1]["eam_task_name"] = p["targets"][0]["eam_task_name"]
        self.check_rejected(p)

    def test_deploy_mode_cannot_authorize_eam(self):
        p = copy.deepcopy(self.profile)
        p["mode"] = "deploy"
        self.check_rejected(p)

    def test_invalid_sha_and_unknown_user_selection_fail(self):
        with self.assertRaises(FrameworkError):
            build_plan(ROOT, self.profile, "short")
        with self.assertRaisesRegex(FrameworkError, "no configured target matched"):
            build_plan(ROOT, self.profile, SHA, gateway="missing-gateway")

    def test_schema_v1_remains_backward_compatible(self):
        p = load_profile(ROOT / "config/example-customer-testlab.json")
        out = build_plan(ROOT, p, SHA)
        self.assertEqual(out["schema_version"], 1)
        self.assertEqual(out["target_count"], 4)


if __name__ == "__main__":
    unittest.main()
