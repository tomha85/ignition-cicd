"""Fork portability and clean-room customer source verification.

These tests intentionally create NEW customer Sites/Factories/Gateways/Projects
in a temporary directory without ANY bundled Warehouse/Factory A resources.
They never open a network connection or contact Ignition/EAM.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.customer_plan import build_plan
from scripts.customer_build_release import make_releases
from scripts.customer_topology import validate_topology

SHA = "c" * 40


def create_project(root, factory, project):
    target = root / "factories" / factory / "projects" / project
    view = target / "com.inductiveautomation.perspective" / "views" / "Main"
    view.mkdir(parents=True, exist_ok=True)
    (target / "project.json").write_text(json.dumps({"title": project}), encoding="utf-8")
    (view / "resource.json").write_text(json.dumps({"files": ["view.json"]}), encoding="utf-8")
    (view / "view.json").write_text(json.dumps({
        "root": {"type": "ia.container.flex", "props": {"direction": "column"}}
    }), encoding="utf-8")


def create_factory(root, factory, gateway_projects):
    dirpath = root / "factories" / factory
    dirpath.mkdir(parents=True, exist_ok=True)
    records = []
    for gateway, projects in gateway_projects.items():
        for project in projects:
            create_project(root, factory, project)
        records.append({
            "gateway_id": gateway,
            "projects": [
                {"name": project, "source": "projects/" + project}
                for project in projects
            ],
            "environments": {
                "test": {
                    "github_environment": gateway + "-test",
                    "deployment_method": "eam",
                    "target_id": gateway + "-test-target",
                    "secret_refs": ["CUSTOMER_EAM_TOKEN"],
                    "deployment_enabled": False,
                }
            },
        })
    (dirpath / "factory.json").write_text(json.dumps({
        "schema_version": 1,
        "factory_id": factory,
        "ignition_version": "8.3",
        "gateways": records,
    }), encoding="utf-8")


def controller():
    return {
        "controller_id": "customer-eam",
        "hosting": "on_prem",
        "controller_url": "https://eam.company.test:8043",
        "network": "site_lan",
        "api_token_secret": "CUSTOMER_EAM_TOKEN",
        "ca_file_variable": "CUSTOMER_EAM_CA",
    }


def target(site, workshop, factory, gateway, project, agent, task, scope, network):
    return {
        "site_id": site,
        "workshop_id": workshop,
        "factory_id": factory,
        "gateway_id": gateway,
        "project": project,
        "controller_id": "customer-eam",
        "agent_name": agent,
        "eam_task_name": task,
        "connection_scope": scope,
        "agent_network": network,
    }


def single_factory_fixture(root):
    create_factory(root, "water-treatment", {
        "water-controls": ["WaterSCADA", "WaterHistorian"],
        "water-utilities": ["PumpDashboard"],
    })
    return {
        "schema_version": 2, "customer_id": "acme-water-company", "mode": "plan_only",
        "controllers": [controller()],
        "sites": [{
            "site_id": "water-campus",
            "display_name": "Water Campus",
            "workshops": ["process", "utilities"],
        }],
        "targets": [
            target("water-campus", "process", "water-treatment",
                   "water-controls", "WaterSCADA", "Controls-Agent",
                   "Send-WaterSCADA", "same_site", "site_lan"),
            target("water-campus", "process", "water-treatment",
                   "water-controls", "WaterHistorian", "Controls-Agent",
                   "Send-WaterHistorian", "same_site", "site_lan"),
            target("water-campus", "utilities", "water-treatment",
                   "water-utilities", "PumpDashboard", "Utilities-Agent",
                   "Send-PumpDashboard", "same_site", "site_lan"),
        ],
    }


def multi_factory_fixture(root):
    create_factory(root, "north-mill", {"mill-controls": ["MillHMI"]})
    create_factory(root, "south-plant", {"plant-controls": ["PlantHMI"]})
    c = controller()
    c.update(hosting="private_cloud", network="private_overlay",
             controller_url="https://eam.cloud.company.test:8043")
    return {
        "schema_version": 2, "customer_id": "acme-regional", "mode": "plan_only",
        "controllers": [c],
        "sites": [
            {"site_id": "north-site", "display_name": "North Mill",
             "workshops": ["mill-floor"]},
            {"site_id": "south-site", "display_name": "South Plant",
             "workshops": ["plant-floor"]},
        ],
        "targets": [
            target("north-site", "mill-floor", "north-mill", "mill-controls",
                   "MillHMI", "Mill-Agent", "Send-MillHMI",
                   "cross_site", "private_vpn"),
            target("south-site", "plant-floor", "south-plant", "plant-controls",
                   "PlantHMI", "Plant-Agent", "Send-PlantHMI",
                   "cross_site", "private_overlay"),
        ],
    }


class CleanRoomCustomerTests(unittest.TestCase):
    def test_one_factory_three_projects_two_gateways_one_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            validate_topology(profile)
            plan = build_plan(root, profile, SHA)
            self.assertEqual(plan["target_count"], 3)
            self.assertEqual(plan["factory_count"], 1)
            self.assertEqual(plan["site_count"], 1)
            self.assertEqual(plan["workshop_count"], 2)
            self.assertEqual(plan["controller_count"], 1)
            self.assertTrue(all(t["stage"] == "NOT_RUN" for t in plan["targets"]))
            self.assertEqual(plan["production"], "HOLD")

    def test_multi_factory_multiple_locations_private_vpn_and_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = multi_factory_fixture(root)
            plan = build_plan(root, profile, SHA)
            self.assertEqual(plan["factory_count"], 2)
            self.assertEqual(plan["site_count"], 2)
            self.assertEqual(plan["target_count"], 2)
            self.assertEqual({t["agent_network"] for t in plan["targets"]},
                             {"private_vpn", "private_overlay"})
            self.assertEqual({t["connection_scope"] for t in plan["targets"]},
                             {"cross_site"})

    def test_one_gateway_carries_two_projects_on_same_eam_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            subset = build_plan(root, profile, SHA, gateway="water-controls")
            self.assertEqual(subset["target_count"], 2)
            self.assertEqual({t["eam_agent_name"] for t in subset["targets"]},
                             {"Controls-Agent"})
            self.assertEqual({t["project"] for t in subset["targets"]},
                             {"WaterSCADA", "WaterHistorian"})

    def test_build_zip_for_each_customer_target_without_demo_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            releases = make_releases(root, profile, SHA, root / "dist")
            self.assertEqual(releases["release_count"], 3)
            self.assertEqual(releases["eam_task"], "NOT_RUN")
            self.assertEqual(releases["production"], "HOLD")
            for item in releases["releases"]:
                archive = root / "dist" / item["archive"]
                self.assertTrue(archive.is_file())
                with zipfile.ZipFile(archive) as z:
                    names = z.namelist()
                    self.assertIn("release-manifest.json", names)
                    self.assertIn(item["project"] + "/project.json", names)
                    manifest = json.loads(z.read("release-manifest.json"))
                    self.assertEqual(manifest["factory_id"], item["factory_id"])
                    self.assertEqual(manifest["gateway_id"], item["gateway_id"])
                    self.assertEqual(manifest["status"], "BUILT_NOT_DEPLOYED")

    def test_customer_wrong_source_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            profile["targets"][0]["project"] = "NotInManifest"
            with self.assertRaises(FrameworkError):
                build_plan(root, profile, SHA)

    def test_customer_cross_site_cannot_declare_lan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = multi_factory_fixture(root)
            profile["targets"][0]["agent_network"] = "site_lan"
            with self.assertRaises(FrameworkError):
                validate_topology(profile)

    def test_customer_agent_cannot_silently_switch_gateway(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            profile["targets"][2]["agent_name"] = "Controls-Agent"
            with self.assertRaises(FrameworkError):
                validate_topology(profile)

    def test_customer_task_name_must_not_be_reused_for_other_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            profile["targets"][2]["eam_task_name"] = "Send-WaterSCADA"
            with self.assertRaises(FrameworkError):
                validate_topology(profile)

    def test_customer_live_deployment_never_authorized_by_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = single_factory_fixture(root)
            profile["mode"] = "deploy"
            with self.assertRaises(FrameworkError):
                validate_topology(profile)


if __name__ == "__main__":
    unittest.main()
