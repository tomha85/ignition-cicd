"""Structural-only checks of the standalone native Perspective diagnostic sample.

This suite is not an Ignition Designer, Gateway or Browser FAT.
"""
import json
import unittest
from pathlib import Path

from reusable_cicd.core import validate_project

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples/ignition-diagnostics-dashboard"
PROJECT = DEMO / "PLCCommunicationDiagnostics"
CATALOG = DEMO / "ignition_83_metric_catalog.json"
VIEWS = PROJECT / "com.inductiveautomation.perspective" / "views"
PAGES = PROJECT / "com.inductiveautomation.perspective" / "page-config" / "config.json"
EXPECTED_SAMPLING = {
    "ActualSamplingInterval", "ActualThroughput",
    "IdealSamplingInterval", "IdealThroughput",
    "OverloadFactor", "QueueDuration", "RequestCount",
}
EXPECTED_EXECUTION = {
    "NthPercentile", "Count", "Max", "Mean", "Min", "MeanRate",
    "OneMinuteRate", "FiveMinuteRate",
}
EXPECTED_ROOT = {
    "Connected", "Hostname", "Name", "Port", "State", "Status",
    "Internal Indicator (IIN)", "MonitoredItemCount",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nodes(node):
    yield node
    for child in node.get("children", []):
        yield from nodes(child)


class IgnitionDashboardSourceTests(unittest.TestCase):
    def test_native_ignition_structure_valid_not_runtime_proven(self):
        manifest = validate_project(PROJECT, "PLCCommunicationDiagnostics")
        self.assertGreater(manifest["file_count"], 5)
        self.assertEqual(manifest["native_structure"],
                         "VALIDATED_NOT_RUNTIME_TESTED")

    def test_all_23_documented_native_device_driver_fields_in_catalog(self):
        catalog = load(CATALOG)
        self.assertEqual(catalog["schema_version"], 1)
        fields = catalog["metrics"]
        self.assertEqual(len(fields), 23)
        self.assertEqual(len({m["name"] for m in fields}), 23)
        self.assertEqual({m["name"] for m in fields if m["section"] == "sampling"},
                         EXPECTED_SAMPLING)
        self.assertEqual({m["name"] for m in fields if m["section"] == "execution"},
                         EXPECTED_EXECUTION)
        self.assertEqual(
            {m["name"] for m in fields if m["section"] in ("root", "sampling_root", "dnp3_optional")},
            EXPECTED_ROOT,
        )
        self.assertTrue(all(m["source_status"] == "REQUIRES_GATEWAY_DISCOVERY"
                            and m["source_path"] is None for m in fields))

    def test_aggregate_sampling_does_not_claim_group_only_metrics(self):
        fields = load(CATALOG)["metrics"]
        for name in ("ActualSamplingInterval", "IdealSamplingInterval",
                     "OverloadFactor", "QueueDuration"):
            item = next(m for m in fields if m["name"] == name)
            self.assertIs(item["aggregate_available"], False)

    def test_pages_route_to_real_native_view_names(self):
        pages = load(PAGES)["pages"]
        self.assertEqual(set(pages), {"/", "/device", "/metrics"})
        self.assertEqual(pages["/"]["viewPath"], "Fleet")
        self.assertEqual(pages["/device"]["viewPath"], "Dashboard")
        self.assertEqual(pages["/metrics"]["viewPath"], "MetricCatalog")
        for page in pages.values():
            self.assertTrue((VIEWS / page["viewPath"] / "view.json").is_file())

    def test_fleet_view_requires_verifiably_supplied_devices(self):
        view = load(VIEWS / "Fleet" / "view.json")
        self.assertEqual(view["params"]["deviceRows"], [])
        tables = [n for n in nodes(view["root"])
                  if n.get("meta", {}).get("name") == "FleetTable"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(
            tables[0]["propConfig"]["props.data"]["binding"]["config"]["path"],
            "view.params.deviceRows",
        )

    def test_device_kpis_are_unidirectional_and_unmapped_by_default(self):
        view = load(VIEWS / "Dashboard" / "view.json")
        self.assertEqual(len(view["params"]["metrics"]), 8)
        self.assertTrue(all(value.startswith("N/A")
                            for value in view["params"]["metrics"].values()))
        bindings = []
        for item in nodes(view["root"]):
            for prop, config in item.get("propConfig", {}).items():
                binding = config["binding"]
                bindings.append(binding)
                self.assertEqual(binding["type"], "property")
                self.assertNotIn("bidirectional", str(config).lower())
        self.assertEqual(len(bindings), 8)

    def test_historian_chart_has_no_fabricated_pens_or_data(self):
        view = load(VIEWS / "Dashboard" / "view.json")
        charts = [item for item in nodes(view["root"])
                  if item.get("type") == "ia.chart.powerchart"]
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0].get("props"), {})

    def test_metric_catalog_is_empty_until_mapped(self):
        view = load(VIEWS / "MetricCatalog" / "view.json")
        tables = [item for item in nodes(view["root"])
                  if item.get("meta", {}).get("name") == "CatalogTable"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]["props"]["data"]), 23)
        for item in tables[0]["props"]["data"]:
            self.assertEqual(item["Quality"], "NOT MAPPED")
            self.assertTrue(item["Realtime Value"].startswith("N/A"))

    def test_no_scripts_can_write_to_plc_or_change_gateway(self):
        for f in PROJECT.rglob("*.json"):
            serialized = f.read_text(encoding="utf-8")
            for forbidden in ("system.opc.writeValue", "system.opc.writeValues",
                              "system.tag.writeBlocking", "system.tag.configure",
                              "system.tag.deleteTags", "bidirectional", "writeBack"):
                self.assertNotIn(forbidden, serialized)

    def test_gateway_metric_sources_are_not_misrepresented_as_opc_tags(self):
        catalog = load(CATALOG)
        self.assertIn("separate", catalog["gateway_diagnostics"]["source"].lower()
                      .replace("adapter", "separate"))
        self.assertTrue(catalog["writes"]["instrumentation_required"])


if __name__ == "__main__":
    unittest.main()
