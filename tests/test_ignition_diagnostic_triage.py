"""Offline fleet diagnostics rules. The script cannot access PLCs/Gateways."""
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PATH = (Path(__file__).resolve().parents[1]
        / "examples/ignition-diagnostics-dashboard/analysis_engine.py")
spec = importlib.util.spec_from_file_location("diagnostic_engine", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def metric(value, quality="GOOD", timestamp=STAMP, source="verified_ignition_diagnostic"):
    return {"value": value, "quality": quality,
            "observed_at": timestamp, "source": source}


def plc(number, server="Ignition OPC UA Server"):
    return {
        "device_id": "PLC-%03d" % number,
        "gateway_id": "customer-gateway",
        "opc_server": server, "protocol": "native_driver",
        "metrics": {
            "connected": metric(True),
            "bad_quality_tag_count": metric(0, source="tag_quality_inventory"),
            "overload_factor_pct": metric(10, source="specific_sampling_group"),
            "response_mean_ms": metric(15, source="aggregate_lifetime_execution"),
            "requests_per_second_1m": metric(100, source="aggregate_execution_1m"),
        },
    }


def sample(devices):
    return {"schema_version": 1, "collected_at": STAMP, "devices": devices}


class IgnitionFleetDiagnosticsTests(unittest.TestCase):
    def test_one_out_of_100_plcs_disconnected(self):
        devices = [plc(i) for i in range(1, 101)]
        devices[16]["metrics"]["connected"] = metric(False)
        result = module.evaluate(sample(devices))
        self.assertEqual(result["device_count"], 100)
        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["device_id"], "PLC-017")
        self.assertEqual(result["findings"][0]["code"], "DEVICE_DISCONNECTED")
        self.assertFalse(result["root_cause_confirmed"])

    def test_shared_opc_fault_is_hypothesis_not_proven_cause(self):
        devices = [plc(i) for i in range(1, 10)]
        for d in devices[:6]:
            d["metrics"]["bad_quality_tag_count"] = metric(5, source="tag_quality_inventory")
        result = module.evaluate(sample(devices))
        self.assertEqual(result["finding_count"], 6)
        self.assertEqual(result["shared_layer_hypotheses"][0]["root_cause"], "NOT_CONFIRMED")
        self.assertEqual(result["gateway_cpu"], "NOT_PROVIDED")
        self.assertEqual(result["plc_cpu"], "NOT_PROVIDED")

    def test_sampling_overload_is_driver_not_plc_cpu(self):
        device = plc(1)
        device["metrics"]["overload_factor_pct"] = metric(125)
        result = module.evaluate(sample([device]))
        finding = result["findings"][0]
        self.assertEqual(finding["code"], "SAMPLING_OVERLOAD")
        self.assertEqual(finding["suspected_layer"], "IGNITION_DRIVER_SAMPLING")
        self.assertEqual(finding["root_cause"], "NOT_CONFIRMED")

    def test_quality_bad_and_stale_values_never_generate_false_overload(self):
        device = plc(1)
        device["metrics"]["overload_factor_pct"] = metric(400, quality="BAD")
        result = module.evaluate(sample([device]))
        self.assertEqual(result["finding_count"], 0)
        self.assertEqual(result["devices"][0]["metric_status"]["overload_factor_pct"],
                         "QUALITY_BAD")
        old = (NOW - timedelta(minutes=10)).isoformat()
        device["metrics"]["overload_factor_pct"] = metric(400, timestamp=old)
        result = module.evaluate(sample([device]))
        self.assertEqual(result["finding_count"], 0)
        self.assertEqual(result["devices"][0]["metric_status"]["overload_factor_pct"],
                         "STALE")

    def test_read_response_lifetime_mean_not_mislabeled_as_spike(self):
        device = plc(1)
        device["metrics"]["response_mean_ms"] = metric(100000)
        result = module.evaluate(sample([device]))
        self.assertEqual(result["finding_count"], 0)

    def test_write_failures_only_from_separately_instrumented_verified_source(self):
        device = plc(1)
        device["metrics"]["write_failure_count_1m"] = metric(
            3, source="explicit_write_audit_pipeline")
        result = module.evaluate(sample([device]))
        self.assertEqual(result["findings"][0]["code"], "WRITE_FAILURES")
        self.assertEqual(result["findings"][0]["root_cause"], "NOT_CONFIRMED")
        self.assertFalse(result["production_control_allowed"])

    def test_duplicate_identity_rejected(self):
        d = plc(1)
        with self.assertRaises(module.DiagnosticInputError):
            module.evaluate(sample([d, d]))

    def test_malformed_and_missing_sources_are_not_success(self):
        device = plc(1)
        device["metrics"] = {}
        result = module.evaluate(sample([device]))
        self.assertEqual(result["devices"][0]["diagnostic_state"], "INSUFFICIENT_DATA")
        self.assertEqual(result["finding_count"], 0)
        self.assertFalse(result["root_cause_confirmed"])


if __name__ == "__main__":
    unittest.main()
