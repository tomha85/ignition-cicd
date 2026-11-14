"""Read-only evidence-based communication diagnostics.

No network, PLC reads/writes, or Gateway calls. The collector that produces
snapshots is separate and MUST be commissioned against each actual Ignition
Gateway. Findings are hypotheses, NEVER confirmed PLC root causes.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite

SUPPORTED_QUALITY = {"GOOD", "BAD", "UNCERTAIN"}
SCHEMA = 1
DEFAULT_STALE_SECONDS = 120
SAMPLING_OVERLOAD_THRESHOLD = 100.0  # per Ignition device-diagnostics definition


class DiagnosticInputError(ValueError):
    pass


def _require(condition, reason):
    if not condition:
        raise DiagnosticInputError("DIAGNOSTIC_INPUT_HOLD: " + reason)


def _timestamp(value):
    _require(isinstance(value, str), "timestamp must be ISO-8601")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DiagnosticInputError("DIAGNOSTIC_INPUT_HOLD: invalid timestamp") from exc
    _require(stamp.tzinfo is not None, "timestamp must include timezone")
    return stamp.astimezone(timezone.utc)


def _metric(device, name, now, *, stale_seconds):
    metric = device.get("metrics", {}).get(name)
    if metric is None:
        return None, "NOT_MAPPED"
    _require(isinstance(metric, dict) and
             set(metric) == {"value", "quality", "observed_at", "source"},
             "invalid metric: " + name)
    quality = metric["quality"]
    _require(isinstance(quality, str) and quality in SUPPORTED_QUALITY,
             "invalid metric quality")
    source = metric["source"]
    _require(isinstance(source, str) and 0 < len(source) <= 120,
             "missing metric provenance")
    observed = _timestamp(metric["observed_at"])
    age = (now - observed).total_seconds()
    if age < -60:
        return None, "FUTURE_TIMESTAMP"
    if age > stale_seconds:
        return None, "STALE"
    if quality != "GOOD":
        return None, "QUALITY_" + quality
    # OverloadFactor exists only in actual sampling group diagnostics,
    # not in the device-wide Aggregate. Prevent unscoped aggregate claims.
    if name == "overload_factor_pct" and not source.startswith("sampling_group:"):
        return None, "MISSING_SAMPLE_GROUP_PROVENANCE"
    value = metric["value"]
    if value is None:
        return None, "NULL"
    if isinstance(value, float) and not isfinite(value):
        return None, "NONFINITE"
    return value, "VERIFIED"


def _issue(code, device, title, evidence, investigate, layer, severity="WARNING"):
    return {
        "code": code, "severity": severity, "device_id": device["device_id"],
        "gateway_id": device["gateway_id"], "opc_server": device["opc_server"],
        "suspected_layer": layer, "title": title,
        "evidence": evidence, "next_checks": investigate,
        "root_cause": "NOT_CONFIRMED", "source": "DETERMINISTIC_RULE",
    }


def evaluate(snapshot, *, stale_seconds=DEFAULT_STALE_SECONDS):
    """Returns per-PLC findings, fleet cohort hints and explicit unknowns.

    The only defined thresholds are vendor's sampling overload semantics and
    source-data nonnegativity. There is no global latency or write-rate
    threshold: site engineers establish baselines first.
    """
    _require(isinstance(snapshot, dict) and
             set(snapshot) == {"schema_version", "collected_at", "devices"},
             "invalid snapshot structure")
    _require(type(snapshot["schema_version"]) is int and
             snapshot["schema_version"] == SCHEMA, "invalid snapshot schema")
    now = _timestamp(snapshot["collected_at"])
    devices = snapshot["devices"]
    _require(isinstance(devices, list) and len(devices) <= 2000,
             "devices must be a list of at most 2000 entries")
    _require(isinstance(stale_seconds, int) and stale_seconds >= 10,
             "invalid maximum data age")
    seen = set()
    findings, inventory, cohorts = [], [], defaultdict(list)
    for device in devices:
        _require(isinstance(device, dict) and
                 set(device) == {"device_id", "gateway_id", "opc_server",
                                 "protocol", "metrics"},
                 "invalid device record")
        for key in ("device_id", "gateway_id", "opc_server", "protocol"):
            _require(isinstance(device[key], str) and 0 < len(device[key]) <= 120,
                     "invalid device " + key)
        _require(isinstance(device["metrics"], dict), "metrics must be a dict")
        identity = (device["gateway_id"], device["opc_server"], device["device_id"])
        _require(identity not in seen, "duplicate device identity")
        seen.add(identity)
        connected, conn_status = _metric(device, "connected", now,
                                         stale_seconds=stale_seconds)
        bad_count, bad_status = _metric(device, "bad_quality_tag_count", now,
                                        stale_seconds=stale_seconds)
        overload, overload_status = _metric(device, "overload_factor_pct", now,
                                              stale_seconds=stale_seconds)
        response, response_status = _metric(device, "response_mean_ms", now,
                                              stale_seconds=stale_seconds)
        rate, rate_status = _metric(device, "requests_per_second_1m", now,
                                      stale_seconds=stale_seconds)
        write_failures, write_status = _metric(device, "write_failure_count_1m", now,
                                                  stale_seconds=stale_seconds)
        vals = {"connected": (connected, conn_status),
                "bad_quality_tag_count": (bad_count, bad_status),
                "overload_factor_pct": (overload, overload_status),
                "response_mean_ms": (response, response_status),
                "requests_per_second_1m": (rate, rate_status),
                "write_failure_count_1m": (write_failures, write_status)}
        for key, (value, status) in vals.items():
            if status == "VERIFIED" and key == "connected":
                _require(type(value) is bool, "connected must be boolean")
            elif status == "VERIFIED":
                _require(type(value) in (int, float) and isfinite(value) and value >= 0,
                         "numeric diagnostic must be nonnegative")
        local_codes=[]
        if conn_status == "VERIFIED" and connected is False:
            findings.append(_issue(
                "DEVICE_DISCONNECTED", device, "Device connection down",
                ["connected=false, Quality=GOOD, timestamp valid"],
                ["Inspect device connection state, OPC server, network and PLC power"],
                "DEVICE_OR_OPC_CONNECTION", "HIGH"))
            local_codes.append("DEVICE_DISCONNECTED")
        if bad_status == "VERIFIED" and bad_count > 0:
            findings.append(_issue(
                "BAD_QUALITY_TAGS", device, "Observed Bad Quality tags",
                ["{} Bad Quality tags from verified source".format(bad_count)],
                ["Inspect affected Tag paths and quality codes", "Review OPC session and logs"],
                "TAG_OR_OPC_SOURCE"))
            local_codes.append("BAD_QUALITY_TAGS")
        if overload_status == "VERIFIED" and overload > SAMPLING_OVERLOAD_THRESHOLD:
            findings.append(_issue(
                "SAMPLING_OVERLOAD", device, "Sampling group cannot keep ideal rate",
                ["Ignition sampling OverloadFactor={}%, above 100%".format(overload)],
                ["Inspect this device sampling groups, RequestCount and QueueDuration",
                 "Compare effective sampling rate with configured Tag Group rate"],
                "IGNITION_DRIVER_SAMPLING", "HIGH"))
            local_codes.append("SAMPLING_OVERLOAD")
        if write_status == "VERIFIED" and write_failures > 0:
            findings.append(_issue(
                "WRITE_FAILURES", device, "Instrumented write failures observed",
                ["{} failed writes in last 1 min (requires separate audited source)".format(write_failures)],
                ["Inspect exact write tags, quality, permissions, response and audit logs",
                 "Review Read After Write settings and write pressure"],
                "OPC_WRITE_PATH", "HIGH"))
            local_codes.append("WRITE_FAILURES")
        # Lifetime Mean isn't a rolling latency value; don't label it 'spike'.
        if response_status == "VERIFIED" and response is not None:
            # The response value is reported, not evaluated as 'slow' without
            # an independent and comparable driver baseline.
            pass
        # Write outcomes and bad-quality aggregates are NOT guaranteed
        # native driver metrics; missing optional instrumentation is normal.
        required_builtin = (
            "connected", "overload_factor_pct",
            "response_mean_ms", "requests_per_second_1m"
        )
        missing = [name for name, (_v, status) in vals.items()
                   if status != "VERIFIED"]
        missing_required = [name for name in required_builtin
                            if vals[name][1] != "VERIFIED"]
        inventory.append({
            "gateway_id": device["gateway_id"], "opc_server": device["opc_server"],
            "device_id": device["device_id"], "protocol": device["protocol"],
            "issue_count": len(local_codes),
            "issues": local_codes,
            "missing_or_invalid": missing,
            "missing_required_builtin": missing_required,
            "diagnostic_state": ("INVESTIGATE" if local_codes else
                                 "NO_ALERT_RULE_TRIGGERED" if not missing_required else
                                 "INSUFFICIENT_DATA"),
            "live_metrics": {
                name: (value if status == "VERIFIED" else None)
                for name, (value, status) in vals.items()
            },
            "metric_status": {name: status for name, (_v, status) in vals.items()},
        })
        if local_codes:
            cohorts[(device["gateway_id"], device["opc_server"])].append(device["device_id"])
    cohort_findings=[]
    # A common shared layer is a triage clue, not proof of its cause.
    for (gateway, server), impacted in sorted(cohorts.items()):
        if len(impacted) >= 3:
            cohort_findings.append({
                "scope": "GATEWAY_OPC_SERVER", "gateway_id": gateway,
                "opc_server": server, "affected_devices": sorted(impacted),
                "potential_shared_layer": ["OPC server", "Ignition Gateway",
                                            "shared network infrastructure"],
                "root_cause": "NOT_CONFIRMED",
                "next_check": "Compare same-time findings and unaffected devices across other OPC servers",
            })
    return {
        "schema_version": SCHEMA, "status": "OFFLINE_EVIDENCE_TRIAGE_ONLY",
        "device_count": len(inventory), "finding_count": len(findings),
        "devices": inventory, "findings": findings, "shared_layer_hypotheses": cohort_findings,
        "gateway_cpu": "NOT_PROVIDED", "plc_cpu": "NOT_PROVIDED",
        "physical_plc_scan_time": "NOT_PROVIDED",
        "production_control_allowed": False, "root_cause_confirmed": False,
    }
