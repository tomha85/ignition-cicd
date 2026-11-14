# Customer configuration checklist (Ignition 8.3 CI/CD)

**This directory contains edit-ready examples, not working EAM connections.**
A successful offline GitHub Actions run is **not** proof that a customer's
Ignition Gateway, EAM Controller/Agent, network, backups or Perspective runtime
is ready for deployment.

## Choose a configuration

| Customer | Copy to `config/customer.json` |
| --- | --- |
| One factory with multiple workshops | [example-single-factory-workshops.json](example-single-factory-workshops.json) |
| Several factories across geographic locations | [example-multi-factory-locations.json](example-multi-factory-locations.json) |
| Mixed multiple workshops/sites/controllers | [example-company-multi-site.json](example-company-multi-site.json) |

All three use **the same code**:
`scripts/customer_topology.py` →
`scripts/customer_plan.py` →
`scripts/customer_build_release.py`.

## What the customer MUST supply

| Input | Customer configuration field / path | Notes |
| --- | --- | --- |
| Company identifier | `customer_id` | Replace example ID |
| Controller logical identity | `controllers[].controller_id` | Exact reference in targets |
| Controller management address | `controllers[].controller_url` | HTTPS base and port; real reachable FQDN/IP |
| Hosting and runner connectivity | `controllers[].hosting/network` | On-prem/private cloud; LAN/VPN/private WAN/overlay |
| API authentication and trusted CA | `controllers[].api_token_secret/ca_file_variable` | **Names only**; values in a protected secret store |
| Facility name and location | `sites[].site_id/display_name` | One site for a multi-workshop factory |
| Workshops | `sites[].workshops[]` | Site-specific workshop IDs |
| Target association | `targets[].site_id/workshop_id/factory_id` | Explicit physical identity |
| Gateway/project | `targets[].gateway_id/project` | Must match the factory manifest and native source |
| Controller↔Agent | `targets[].controller_id/agent_name` | Must already exist and be independently verified |
| Existing EAM Send Project task | `targets[].eam_task_name` | Task must be reviewed for exact project and Agent |
| Network relation | `targets[].connection_scope/agent_network` | Cross-site: VPN/private WAN/overlay, not LAN |
| Native Ignition project source | `factories/<factory-id>/projects/<ProjectName>/` | Actual Ignition `project.json` and resource files |
| Registered Gateway/project | `factories/<factory-id>/factory.json` | Environment and target IDs must match |
| Optional documented PLC/OPC/DB/Gateway inventory | `factories/<factory-id>/connections/*.json` | Documentation only; **does not provision** these connections |

A company can maintain a **private fork** and add as many explicit
factory/workshop records as fit the validated bounds. The current v2 contract
permits up to 100 Controllers, 200 Sites and 500 target project assignments.
Large native-source builds can be limited by CI time/storage; split deployments
by exact target after commissioning. Never publish real OT topology publicly.

## Validate the customer inputs (NO Gateway writes)

```bash
python scripts/verify_customer_checkout.py \
  --sha "$(git rev-parse HEAD)"

python scripts/customer_readiness.py \
  --config config/customer.json \
  --sha "$(git rev-parse HEAD)" \
  --require-customer-input \
  --output evidence/customer-readiness.json

python scripts/customer_plan.py \
  --config config/customer.json \
  --sha "$(git rev-parse HEAD)" \
  --output evidence/customer-plan.json

python scripts/customer_build_release.py \
  --config config/customer.json \
  --sha "$(git rev-parse HEAD)" \
  --output-dir dist/customer-releases \
  --evidence evidence/customer-release-manifest.json
```

`--require-customer-input` fails when the selected profile still
contains obvious example values; it **does not** validate actual network
reachability or EAM task registration. If you still use the bundled example
project folders, replace the native sources and matching manifests before
claiming customer setup.

On GitHub, run **Customer CI - Validate Configured Sites (NO DEPLOY)**, which
also produces a downloadable readiness JSON and native ZIP evidence. No EAM
task runs. The other EAM workflows are intentionally restricted to this
repository's local two-container TEST Lab and are not the customer deploy path.

## Before a real deployment can be qualified

The current repository **DOES NOT have a qualified customer remote EAM
deployer**. To deploy to a live customer TEST Gateway, the installer/engineer
must separately provide and verify a trusted network-connected runner,
EAM Controller API permissions and trust, installed/registered Agents and
pre-reviewed Send Project tasks, tested backup/restore procedure, and test
Gateway/Perspective FAT checks. Production still requires approvals and real
PLC/OPC UA validation. This configuration **cannot** grant these permissions
by changing `mode`; it is intentionally `plan_only`.

See [Customer setup](../docs/CUSTOMER_SETUP.md) and
[the two topology reference designs](../docs/CUSTOMER_TOPOLOGY.md).
