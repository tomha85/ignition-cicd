# Portable customer topology — sites, workshops, EAM on-prem or private cloud

The CI/CD engine is **customer-agnostic for source validation and TEST planning**.
A company can have multiple workshops at the same location, multiple factories
in different locations, and one or more EAM Controllers hosted on-prem or in a
private cloud. The **same versioned schema** is used in each case.

> Safety boundary: this configuration is **NOT** permission to deploy.
> The local two-container Factory A TEST integration remains a separate demo.
> Customer EAM delivery, network reachability and runtime/FAT are **NOT VERIFIED**.

## What to configure

1. Export **real Ignition 8.3 native project resources** into
   `factories/<factory-id>/projects/<ProjectName>`.
2. Declare Gateway/Project membership and environments in each
   `factories/<factory-id>/factory.json`.
3. Copy `config/example-company-multi-site.json` to your private
   company profile and edit **only customer-specific values**:
   - `customer_id` — organizational ID
   - `controllers[]` — on-prem or private-cloud Controller IDs,
     HTTPS management base URLs, private network type, secret/CA variable names
   - `sites[]` — site IDs, display labels, workshop IDs
   - `targets[]` — exact Site + Workshop + Factory + Gateway + Project +
     EAM Controller ID + Agent name + already-configured EAM Send Project task name
4. Maintain Gateway/DB/PLC/OPC UA **connection inventory separately** per
   factory as documented in [Factory connections](FACTORY_CONNECTIONS.md).
   Those files do not establish live OPC UA connections.
5. Set up private connectivity, HTTPS certificate trust and Ignition Gateway
   Network/EAM membership outside GitHub. Keep tokens, private keys and
   real OT topology out of public repositories.

**Multiple workshops at one location**: reuse the same `site_id`, give
each workshop its own `workshop_id`, and map its exact target Gateway.

**Factories across locations**: give each location its own `site_id`,
then link its targets to the appropriate Controller.

**EAM on-prem or in a cloud**: set Controller `hosting` to `on_prem`
or `private_cloud` and use an HTTPS endpoint reachable from a
trusted deployment runner over `site_lan`, `private_vpn`,
`private_wan` or `private_overlay`. Declaring a network mode
does not create a VPN, tunnel or firewall rule. EAM's Gateway Network also
requires its own verified trust/connectivity.

**Multiple Controllers**: define each controller once and reference
`controller_id` in each target. A single network's EAM roles and
trust boundaries must follow Ignition's supported Controller/Agent topology;
do not create overlapping or circular Gateway Networks.

## Example deployment target

```json
{
  "site_id": "headquarters-campus",
  "workshop_id": "utilities-shop",
  "factory_id": "lab-assembly",
  "gateway_id": "utilities-main",
  "project": "PackagingHMI",
  "controller_id": "hq-controller",
  "agent_name": "Utilities-Agent-EXAMPLE",
  "eam_task_name": "SEND-PackagingHMI-EXAMPLE"
}
```

Example names and `.example.invalid` URLs are **nonfunctional**.
The real task must exist, must be reviewed, and must target exactly the intended
EAM Agent before any execution.

## Validate a multi-site customer configuration

```bash
python -m unittest discover -s tests -p 'test_customer_topology.py' -v
python scripts/customer_plan.py \
  --config config/example-company-multi-site.json \
  --sha "$(git rev-parse HEAD)" \
  --output evidence/company-plan.json
```

The plan includes source hashes, `site_id`, `workshop_id`,
`controller_id`, hosting type and Agent/task identifiers, but **never
contains API tokens, CA file values or Controller URL**. It declares:

- `VALIDATED_NOT_DEPLOYED`
- `network_access=NOT_VERIFIED`
- `eam_task_binding=NOT_VERIFIED`
- `eam_send_project=NOT_RUN`
- `production=HOLD`

The hosted workflow `Customer Framework - Multi-Factory TEST Lab Demo
(NO DEPLOY)` validates both the original v1 and portable v2 examples.

## Optional real network preflight (TLS only)

Run manually from a **trusted machine or dedicated deployment runner** that
already has a route to the chosen Controller over the company's private LAN,
VPN, WAN, or private-cloud overlay. Supply the actual trusted CA certificate
file locally; the file path must not be committed.

```bash
python scripts/customer_network_preflight.py \
  --config config/example-company-multi-site.json \
  --controller hq-controller \
  --ca-file /path/to/trusted/controller-ca.crt \
  --confirm READ_ONLY_TLS_PREFLIGHT
```

This performs a **TLS handshake only**, without HTTP, EAM authentication or
project deployment. A pass proves HTTPS reachability and certificate trust
from that machine; it does **not** prove Agent registration, EAM task
configuration, permission to deploy, or PLC communication.

## Production deployment requirements (NOT IMPLEMENTED)

A reusable live adapter must be qualified on a separate customer-like Ignition
TEST Gateway with correct TLS, least-privilege credentials, exact EAM task and
Agent validation, backups/restores, immutable source verification, server/Agent
resource comparison, EAM task-history proof, browser-rendered Perspective FAT
and independent engineering approval. Do not bypass the lab security gates or
claim full deployment simply because the source plan succeeded.

Ignition EAM Send Project replaces the target Agent project but does **not**
install Gateway-level Tags, Tag Providers, OPC UA connections or database
connections; configure and test those independently.

References:
- [Ignition EAM overview](https://www.docs.inductiveautomation.com/docs/8.3/ignition-modules/enterprise-administration)
- [Send Project task](https://www.docs.inductiveautomation.com/docs/8.3/ignition-modules/enterprise-administration/agent-tasks/send-project)
