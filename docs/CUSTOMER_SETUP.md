# Reusable customer setup: one framework, many factories

This repository is a **standard Ignition 8.3 native-project CI/CD framework**.
The included Factory A EAM integration is **lab-specific**, not a generic production deployer.

## Customer onboarding (configuration + actual native project source)

Use a **private fork** for any real plant network inventory.

1. Place exported native Ignition projects under `factories/<factory-id>/projects/<ProjectName>/` with their real `project.json` and `resource.json` files.
2. Edit `factories/<factory-id>/factory.json` to declare the company's Gateways, projects and environment target references. Add factories/Gateways as necessary.
3. Populate `factories/<factory-id>/connections/{gateways,databases,opcua,plc-devices}.json` from customer-supplied, verified information. These are **read-only metadata**, not installers for Gateway, DB or PLC connections. See [Factory connections](FACTORY_CONNECTIONS.md).
4. Copy `config/example-customer-testlab.json` to a customer-specific file. Update `customer_id` and each `(factory_id, gateway_id, project)` target, plus `eam.controller_url`, `eam.agent_name` and `eam.network` (private VPN/WAN). The example uses `.example.invalid` hosts, not real server addresses.
5. Configure VPN routing, Gateway Network TLS/certificate trust, EAM Controller and Agents externally. Store credentials in GitHub secrets/secret manager; JSON contains only reference **names**, never secret values.
6. Run source/config validation before connecting to any customer Gateway.

One `targets[]` record means **one project on one Gateway**, so a factory can have many Gateways and a project may explicitly target a particular Gateway.

## Multiple locations, workshops or cloud-hosted EAM

For a company with multiple workshops at one location, multiple remote
factories, or EAM Controllers running on-prem or in a private cloud, use
[the portable v2 topology guide](CUSTOMER_TOPOLOGY.md) and the
[v2 example profile](../config/example-company-multi-site.json).
Select exact Site → Workshop → Gateway → Project; all dispatch plans remain
read-only until a separately qualified customer deployment adapter exists.

## Use your own customer profile in GitHub Actions

Copy the [multi-site example](../config/example-company-multi-site.json) to
[`config/customer.json`](../config/customer.json), replace the example
site/workshop/controller/Agent values and add actual native project sources.
Then open **Actions → Customer CI - Validate Configured Sites (NO DEPLOY)**
and choose `config/customer.json` (or another approved `config/*.json`).
On PRs, the default customer profile is checked automatically. This workflow
computes factory/site/workshop/target counts **from the customer's profile**,
not from the bundled three-factory demonstration.

Configuration-only CI is separate from commissioning Ignition EAM network
connections, configuring Agent tasks, trusting certificates, backing up
Gateways and proving live Send Project success. Never paste secrets into JSON.

## Run the hosted TEST Lab planning demo (safe, no PLC access)

```bash
python framework/cli/check_repo.py
python -m unittest discover -s tests -p 'test_customer_plan.py' -v
python scripts/customer_plan.py \
  --config config/example-customer-testlab.json \
  --sha "$(git rev-parse HEAD)" \
  --output evidence/customer-testlab-plan.json
```

In GitHub Actions choose **Customer Framework - Multi-Factory TEST Lab Demo (NO DEPLOY)**.
It runs on `ubuntu-latest` with **no runner credentials and no OT network access**. It validates the three sample factories / four site targets, outputs source hashes and uploads a JSON evidence artifact. The result explicitly says `VALIDATED_NOT_DEPLOYED`, `NOT_TESTED` and `HOLD`.

To plan one site, append e.g. `--factory lab-assembly --gateway utilities-main --project PackagingHMI`. This proves precise target selection when the same project appears on multiple Gateways.

## See the actual Factory A EAM TEST Lab workflow (existing)

The existing **Ignition EAM - Select Factory & Project (TEST)** workflow on this repository's `main` has a separately protected Factory A path: validate → `ignition-test` approval → back up local TEST project trees → stage/scan the Docker TEST EAM Controller → optionally invoke the preconfigured EAM Send Project task for `WarehouseHMI` → verify Agent resources.

This **must not** be re-used unchanged on another customer or production Gateway. It still has explicit `tomha85` repository/reviewer authorization, a lab-specific runner and localhost/Docker controller binding. Removing guards is not a substitute for commissioning a new customer EAM adapter.

## Current capability boundary

| Goal | Status |
| --- | --- |
| Customer-defined factories, Gateways and native projects | Source validation supported |
| Customer-defined EAM endpoint, Agent name and private network | Read-only config validation and plan supported |
| Hosted GitHub Actions demo with evidence | Supported; no Gateway writes |
| Real EAM TEST Controller + Agent demonstration | Factory A lab only |
| Arbitrary customer EAM remote deployment by editing JSON only | **Not yet commissioned** |
| Production Gateway or PLC connection changes | **HOLD** |

Before a general-purpose remote EAM deployment can be enabled, add and qualify a vendor-supported Controller adapter, per-customer authorization, recoverable Gateway backups, secure private network access, exact EAM task binding, independent Agent verification, browser FAT and engineering approvals.

**Principle:** TEST Lab demonstrates the workflow; each customer's EAM/PLC/network behavior must be independently verified.
