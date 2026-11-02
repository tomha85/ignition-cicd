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

- **Factory:** ID of a folder under `factories/` (e.g. `lab-warehouse`).
- **Project:** exact native project declared in that factory's `factory.json`
  (e.g. `WarehouseHMI` or `FactoryASmoke`).

These two fields accept text rather than a fixed list because GitHub's native
`workflow_dispatch` form cannot dynamically populate dependent dropdowns.
New factories/projects require reviewed manifests and target onboarding, not
another YAML options update.

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
