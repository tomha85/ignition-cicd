# Customer onboarding & deployment readiness audit — 2026-11-14

**Verdict: Ready to accept configuration for offline validation and native ZIP
builds; NOT READY to deploy to arbitrary customer EAM Controllers/Agents.**

This is a source/CI audit of Ignition 8.3 customer onboarding. It is **not**
runtime commissioning evidence. No customer network, credentials, PLC,
Gateway, EAM task or Perspective session was accessed as part of this audit.

## Scope and tested boundaries

| Gate | Audit conclusion | Evidence / limitations |
| --- | --- | --- |
| Single Factory, multiple Workshop/Gateway/Project IDs | **PASS — offline** | Clean-room fixture in `tests/test_customer_cleanroom.py` |
| Multiple factories, remote locations and VPN/overlay configuration | **PASS — offline** | Clean-room fixture with entirely new Factory/Project names |
| One EAM Agent delivering multiple projects to one Gateway | **PASS — mapping only** | Explicit task per project, never infer project placement |
| No lab Warehouse dependence in customer source plan/release builder | **PASS — offline** | Temporary `water-treatment`, `north-mill`, `south-plant` sources |
| Malformed/malicious JSON types and mismatched mappings | **PASS — fail closed** | Type-guard regression tests |
| Native source SHA/ZIP release generation | **PASS — structural** | ZIP evidence is not Ignition Runtime/FAT |
| Customer fork skips hardcoded Warehouse regression workflows | **Guarded in YAML** | Requires an independent actual fork TEST to prove GH environment behavior |
| Customer input completeness | **PASS — reportable** | `customer_readiness.py` marks examples as `CUSTOMER_INPUT_REQUIRED` |
| Controller management endpoint TLS | **CLI available; customer NOT TESTED** | Optional handshake only from trusted runner, not EAM auth |
| EAM Controller API authentication / task discovery | **NOT TESTED** | Customer Controller/Agent runtime not accessible |
| Gateway Network trust / Agent registered and healthy | **NOT TESTED** | Network fields are descriptions, not connectivity |
| EAM Controller native project staging from customer runner | **NOT IMPLEMENTED** | LAB Docker staging is deliberately isolated |
| Actual EAM Send Project + exact target verification | **NOT QUALIFIED** | Framework generic adapter explicitly raises HOLD |
| Full Gateway backup/restore drills and production-safe rollback | **NOT VERIFIED** | LAB project-directory tar is not full Gateway backup |
| Perspective Browser FAT / tag bindings / quality | **NOT TESTED** | Must test on isolated Gateway; fake mappings forbidden |
| Production deployment | **HOLD** | Independent engineer approval and physical source validation required |

## Changes introduced after review

1. Separate Lab-only GitHub Actions jobs from customer fork CI. These must
   **never** run on a customer's fork or reach customer OT networks.
2. Use `customer-config-ci.yml` as the customer entry point. It only
   reads `config/customer.json` (or an explicitly selected approved
   `config/*.json`), validates exact Factory/Gateway/Project source
   membership, builds native ZIPs and uploads evidence.
3. Add clean-room regression tests that create unrelated customer projects in
   temporary directories. No local two-container lab is required.
4. Reject malformed topology types without raw Python type errors.
5. Fix validated v2 target-count vs native release count mismatch (up to 500
   configured targets). CI time/storage requirements still apply to large
   real project sources.
6. Add `customer_readiness.py` and a CI readiness artifact that
   distinguishes sample placeholder input from customer-provided configuration.
   It **never returns EAM deployment authorization**.

## Customer usage after providing genuine inputs

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

Only after this offline phase, an authorized engineer may perform **separate**
network/TLS, Gateway Network, EAM task and runtime tests with verified customer
endpoints. A successful GitHub Actions job or ZIP hash is **not** a deployment.

See [Customer input checklist](../config/README.md),
[Single Factory / Multi Workshop example](../config/example-single-factory-workshops.json)
and [Multi Factory / Multi Location example](../config/example-multi-factory-locations.json).

## Required P0 acceptance tests before any customer deployment claim

1. **Customer-fork TEST:** from a fresh repository with all lab factories
   removed, input only new factory manifests/native projects and customer
   EAM configuration; run GitHub Actions and verify no hardcoded lab failures.
2. **Independent isolated Ignition TEST Gateway + EAM Controller/Agent:**
   prove supported remote Controller project staging (or approved native
   resource import) using real Controller API/host mechanisms, source SHA and
   exact file verification.
3. **Mandatory backups and recovery:** before *any* write, prove full native
   Gateway backups can be verified and restored. LAB project tar archives are
   insufficient evidence for production recovery.
4. **EAM security and target binding:** use tested TLS/CA, scoped API keys,
   positive Controller/Agent identity, reviewed EAM task definition,
   source project identity and exact Agent association.
5. **EAM delivery, Agent and Browser FAT:** independently prove Send Project
   task completed, Agent project/resources match, Perspective view renders,
   tags/quality/runtime behavior are correct and alarms/critical actions are
   safe. Simulator/fake OPC UA evidence must not imply physical PLC validation.
6. **Approval-controlled promotion:** enforce GitHub environment reviewer,
   immutable approved SHA, least privilege, audit logs, manual release scope,
   backup and rollback plans. Production stays HOLD until site engineers sign off.

These are **release gates**, not optional documentation changes. Do not enable
a generic deployment mode by changing `mode=plan_only` to `deploy`;
the current engine rejects that change intentionally.

## Vendor reference

- [Ignition 8.3 EAM Send Project](https://www.docs.inductiveautomation.com/docs/8.3/ignition-modules/enterprise-administration/agent-tasks/send-project):
  a Send Project replaces the destination Agent project; Gateway-level
  database connections, Tag Providers and security require separate configuration.
- [Ignition 8.3 Gateway OpenAPI](https://www.docs.inductiveautomation.com/docs/8.3/platform/gateway/openapi):
  API capabilities and permission requirements must be checked against each
  actual Gateway, and mutative requests can affect critical configuration.
- [Ignition 8.3 Gateway Network](https://docs.inductiveautomation.com/docs/8.3/platform/gateway-network):
  EAM Controller ↔ Agent requires explicitly configured Gateway Network trust.
