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

## Source-only factory connection metadata

Gateway IP/hostname, database host and credential alias, OPC UA endpoint and
PLC inventory now belong under each `factories/<id>/connections/` directory.
Repository CI checks these four files as part of Validate, including
Factory/Gateway/environment compatibility and no embedded credentials.
They **do not** configure live Ignition connections during Stage. See
[Factory Connections](FACTORY_CONNECTIONS.md).

## Standard manual deployment — Factory + Project only

Open GitHub Actions → **Ignition EAM - Select Factory & Project (TEST)** →
**Run workflow**, branch `main`. Choose:

- **Factory:** ID of a folder under `factories/` (e.g. `lab-warehouse`).
- **Project:** exact native project declared in that factory's `factory.json`
  (e.g. `WarehouseHMI` or `FactoryASmoke`).

**Both fields are native GitHub Actions dropdowns (choice)**, restored
for operator convenience. Their lists are generated from the registered
`factories/*/factory.json` manifests using:

```bash
python scripts/sync_workflow_choices.py
python scripts/sync_workflow_choices.py --check
```

When onboarding a factory or project, run the generator and commit the generated
workflow YAML in the same PR. The validation job checks for catalog/UI drift
and fails rather than hiding new projects. No new factory/project names should
be manually coded into the deploy engine or workflow list.

GitHub's native workflow_dispatch does **not support dependent choice inputs**:
the Project dropdown shows the union of registered project names across all
factories. Validate rejects projects that do not belong to the selected
Factory, or have ambiguous Gateway mappings. The operator still supplies only
Factory + Project. A truly cascading, live-filtered form would require a
separate web UI or app; it is not provided by native GitHub Actions.

`Action` and `Gateway ID` are **not** user inputs. The Validate job
consults the selected factory's `factory.json`, deterministically resolves
a single Gateway for the chosen project, and verifies the TEST environment.
For example, Factory A `FactoryASmoke` resolves to `warehouse-main`.

**Ambiguous mapping:** `lab-assembly/PackagingHMI` belongs to both
`assembly-main` and `utilities-main`. This must fail with
`AMBIGUOUS_GATEWAY`. No Gateway is invented or chosen by position.

Exactly **two GitHub jobs** appear: Validate → Stage. The release planner
checks the selected project under its uniquely resolved Gateway. It then reads
`targets/lab-targets.json` for a **commissioned isolated TEST Controller**
with `controller_stage_approved=true` and
`project_scope=all_manifest_projects`. This authorizes every native project
on that verified Gateway, **not one hardcoded project name**.

Currently the reviewed local `lab-warehouse/warehouse-main` target permits
**both `WarehouseHMI` and `FactoryASmoke`** to stage after
`ignition-test` Required Reviewer approval. All other Gateways remain
**validate-only** until their real TEST Controller/Agent, HTTPS scan endpoint,
backup location and isolation are commissioned in the target registry.

After **Approve and deploy**, Stage revalidates the manifest and target,
verifies the exact Git commit, archives Controller + Agent project directories,
compares source files, stages on the isolated Controller and scans via HTTPS.
No EAM Agent task runs, no real PLC mapping is proven, and production remains HOLD.

The legacy `deploy-test.yml` and `reusable-deploy.yml` remain callable
for existing integrations but are not additional boxes in this manual UI.

## Status

The underlying Factory A stage adapter passed a real update in GitHub run
41504512471. The new generic Controller stage adapter requires a fresh GitHub-approved
`workflow_dispatch` test before claiming full end-to-end deployment PASS.

Production HOLD. Test Gateway real PLC/OPC UA/FAT separately.
