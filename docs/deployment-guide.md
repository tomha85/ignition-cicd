# Standard V3 TEST staging workflow

## Native approval with only two jobs

Factory A smoke runs **Validate** followed by **Stage**.
Both `main` and the development feature branch use the same mandatory
`ignition-test` reviewer gate; no Agent task is run. Stage has a GitHub
`ignition-test` protected Environment; it **WAITs for tomha85's approval**.
Click **Review deployments → Approve and deploy** to start the existing
backup, Controller-stage and verification steps. No separate reviewer-check
job appears.


**Mandatory reviewer gate:** [Configure GitHub Required reviewers, then
Validate → Review deployments → Approve and deploy → Controller staging]
(APPROVAL_WORKFLOW.md). **The existing `ignition-test` Environment must
require `tomha85` review in GitHub Settings.** YAML cannot configure reviewers.
The Controller stage script independently verifies the current-run review and
refuses any writes until approved.

The standard source layout has four workflow entrypoints:
`validate.yml` (read-only source/manifest checks), `build-release.yml`
(reproducible native project ZIP + immutable source SHA), `deploy-test.yml`
(reusable wrapper), and `reusable-deploy.yml` (guarded Controller stage).
Existing prior workflows remain for backward compatibility.

## Standard manual deployment — Factory + Project only

Open GitHub Actions → **Ignition EAM - Select Factory & Project (TEST)** →
**Run workflow**, branch `main`. Choose:

- **Factory:** `lab-warehouse`, `lab-assembly`, or `lab-packaging`.
- **Project:** exact registered Ignition project name (e.g. `FactoryASmoke`).

`Action` and `Gateway ID` are **not** user inputs. The Validate job
consults the selected factory's `factory.json`, deterministically resolves
a single Gateway for the chosen project, and verifies the TEST environment.
For example, Factory A `FactoryASmoke` resolves to `warehouse-main`.

**Ambiguous mapping:** `lab-assembly/PackagingHMI` belongs to both
`assembly-main` and `utilities-main`. This must fail with
`AMBIGUOUS_GATEWAY`. No Gateway is invented or chosen by position.

Exactly **two GitHub jobs** appear: Validate → Stage. For the sole
commissioned TEST source `lab-warehouse/FactoryASmoke`, Stage uses the
protected `ignition-test` Environment to **WAIT** for `tomha85` review.
After **Approve and deploy**, Stage verifies the reviewed commit,
backs up the Controller and Agent project directories, stages native
Ignition resources on the isolated Controller, and checks hashes + scan.
Factory B/C, or the uncommissioned `WarehouseHMI`, validate but Stage
is **Skipped**. No EAM Agent task runs and production stays HOLD.

The legacy `deploy-test.yml` and `reusable-deploy.yml` remain callable
for existing integrations but are not additional boxes in this manual UI.

## Status

The underlying Factory A stage adapter passed a real update in GitHub run
41504512471. The V3 manual nested-call path must be verified by an actual
`workflow_dispatch` run before declaring that route fully proven.

Production HOLD. Test Gateway real PLC/OPC UA/FAT separately.
