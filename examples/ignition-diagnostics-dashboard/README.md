# Ignition 8.3 PLC Communication Diagnostics — Native Perspective Candidate

**Engineering candidate — source-validated only.** This is a separate Ignition
Perspective project intended for any customer Factory, Site, Workshop, Gateway
or fleet of PLC connections. It does not depend on the repo's Factory A
two-container EAM demo.

**This candidate DOES NOT automatically connect to Ignition/PLC devices or
provision Tag Historian pens.** No Browser FAT, Ignition Designer load or
Gateway integration has been completed. All example metric values remain
`N/A / NOT MAPPED` until verified local sources are provided.

## Screens / routes

| Route | View | Purpose |
| --- | --- | --- |
| `/` | `Fleet` | Multi-PLC overview (customer-provided rows), ordered by Gateway / OPC server / device |
| `/device` | `Dashboard` | Device KPI cards, Historian Power Chart and evidence/investigation panel |
| `/metrics` | `MetricCatalog` | 23 documented fields from the native Ignition 8.3 driver diagnostics catalog |
| `/gateway` | `Gateway` | Gateway CPU, heap, threads, Tag Group execution, DB/OPC and Historian source categories (requires separate trusted adapter) |

Project source: `PLCCommunicationDiagnostics/` (native Perspective
`project.json`, `resource.json`, `view.json` and page config).

## Use only real built-in Ignition device diagnostics first

Vendor documentation:
[Ignition 8.3 OPC UA Drivers](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/opc-ua/opc-ua-drivers)

`ignition_83_metric_catalog.json` describes all 23 vendor-documented
native driver fields. It documents **semantics**, not OPC Item Paths.

| Category | Documented fields | Important distinctions |
| --- | --- | --- |
| Root / device status | Connected, Hostname, Name, Port, State, Status | This is device↔OPC status, not PLC CPU |
| Driver-specific | Internal Indicator (IIN) | DNP3 family only; 8.3.4+ |
| Subscriptions | MonitoredItemCount | Includes diagnostic monitored items |
| Sampling | ActualSamplingInterval, ActualThroughput, IdealSamplingInterval, IdealThroughput, OverloadFactor, QueueDuration, RequestCount | Group-specific four metrics are **not** in Aggregate; request count ≠ number of Tags |
| Execution | NthPercentile, Count, Max, Mean, Min, MeanRate, OneMinuteRate, FiveMinuteRate | Mean/Min/Max/Count refer to lifetime of group/device initialization; 1m/5m rates are rolling |

**Sampling groups must be discovered.** There can be `250ms`,
`1000ms` or other group folders depending on actual subscriptions.
Do not assume a fixed group name for every PLC.

**External OPC UA/Kepware:** native Ignition device-driver metrics cannot
simply be applied to external servers; use their specific server/client
diagnostics and document missing coverage separately.

## Bind data safely in a customer TEST Gateway

1. In Gateway **Connections → Devices → Connections**, inspect device status
   and **View Details**. In Designer **Tag Browser → Browse Devices**, find the
   device's actual built-in **Diagnostics** nodes. Different drivers have
   different paths and optional metrics. **Do not invent OPC Item Paths**.
2. First commission **one device** on an isolated Gateway. Copy/import only
   the documented diagnostic tags you actually observe. Create a normalized
   read-only Tag folder outside the PLC production control namespaces, or bind
   directly to those existing real tags. Preserve full source, status, Quality,
   Timestamp, and selected sampling-group identity for each metric.
3. In `Dashboard`, the eight KPI labels are unidirectional bindings
   to `view.params.metrics`, not PLC tags. Bind these parameters
   from the **verified** local Tag sources using Designer or pass them via a
   reusable Embedded View. Supply the corresponding data-quality/status
   evidence independently. An OPC/BAD/STALE quality must **never** be shown
   as a healthy numeric value.
4. For `MetricCatalog`, populate `view.params.metricRows` with **all 23** discovered and quality-qualified diagnostic values. For `Dashboard`, also populate `view.params.samplingGroupRows` by the **actual** sampling group (e.g. a browsed 1000ms group); never collapse group-only OverloadFactor into an Aggregate field.
5. For `Gateway`, populate `view.params.gatewayRows` only from a commissioned Gateway Diagnostics adapter; this is a different information source from device OPC diagnostics.
6. For `Fleet`, provide `view.params.deviceRows` from
   commissioned Tag or Named Query data. A device row should include Gateway,
   OPC server, Device ID, status, metric Quality, last timestamp, and the
   last observed numeric values. Its default is intentionally empty.
7. Enable Historian **only for approved diagnostic Tags**. In the
   `Dashboard` Power Chart, choose actual historian-backed pens,
   e.g., OneMinuteRate, Mean, QueueDuration or OverloadFactor for a
   **specific** device/group. Do not assume the Power Chart auto-creates
   history. A licensed Historian provider is required.
8. Only after TEST Gateway validation, compare short realtime windows with
   1h/24h/7d history; use proper time zones, Quality filters, event timelines
   and connection-reset markers. Record a baseline before tuning any Tag Group.

Use conservative sample rates initially. Adding extra OPC diagnostic tags
also adds monitored subscriptions and can itself change monitored-item
counts; validate overhead on a few devices before extending to 100+ PLCs.
Do not enable DEBUG/TRACE logging continually in production.

For Tag History:
[Perspective Tag History Binding](https://docs.inductiveautomation.com/docs/8.3/ignition-modules/perspective/working-with-perspective-components/bindings-in-perspective/tag-history-bindings-in-perspective)
and [Power Chart](https://docs.inductiveautomation.com/docs/8.3/appendix/components/perspective-components/perspective-chart-palette/perspective-power-chart).

## Gateway-specific diagnostics (separate adapter)

Gateway Diagnostics → Performance, Metrics Dashboard, Execution, Threads and
Logs expose another family of information. Some metrics (Gateway CPU,
memory, thread usage, Tag Group execution, DB throughput, Gateway Network)
do **not** automatically exist as OPC Tag Paths. They require a
supported, authenticated data-collection adapter before inclusion in
Perspective. This project does **not** claim those have been connected.

## Root-cause interpretation — NEVER infer physical PLC internals

The optional offline `analysis_engine.py` illustrates evidence
triage, not live root cause. It uses supplied timestamped/quality-qualified
observations and returns `NOT_CONFIRMED` for all causal hypotheses.

| Observed condition | Investigation priority | What it does NOT establish |
| --- | --- | --- |
| One of 100 devices disconnects | Device connection, network path, OPC server, PLC power | PLC program bug proven |
| One sampling group OverloadFactor > 100% | Requested rates, queue time, item count, shared load | PLC CPU saturation |
| Many devices on same OPC server degrade together | Shared OPC server, Gateway load, network | Exact common failure point |
| Response Mean increases | Driver connection, request queue, baseline, resets | A rolling-latency spike (Mean is lifetime) |
| Read values good but write failed | Separately instrument write acknowledgements + audit | Built-in read sampling proves write success |

**No PLC CPU or Scan Time is inferred from Ignition driver request timing.**
Writes to PLCs are expressly outside this dashboard. Instrumented write
failure counts are **optional**, not guaranteed built-in native diagnostics.

## Quality gates and current boundaries

```bash
python -m unittest discover -s tests -p 'test_ignition_dashboard_source.py' -v
python -m unittest discover -s tests -p 'test_ignition_diagnostic_triage.py' -v
```

These tests validate structural JSON, catalog coverage, intentionally
empty live inputs, 100-PLC offline finding isolation, bad/stale Quality
handling and the absence of control commands.

**Not yet validated:** actual Ignition Designer import/open, Gateway
deployment, Perspective browser render, tag read Quality, historian queries
or performance with real PLC load. A successful CI check does not prove
any of these runtime properties.

Current state: `NATIVE_PROJECT_SOURCE_CANDIDATE` —
`GATEWAY_FAT_NOT_TESTED` — `PRODUCTION_HOLD`.
