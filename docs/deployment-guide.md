# Standard V3 TEST staging workflow

The standard source layout has four workflow entrypoints:
`validate.yml` (read-only source/manifest checks), `build-release.yml`
(reproducible native project ZIP + immutable source SHA), `deploy-test.yml`
(reusable wrapper), and `reusable-deploy.yml` (guarded Controller stage).
Existing prior workflows remain for backward compatibility.

## How to use today — already registered manual entrypoint

GitHub Actions → **Ignition EAM - Multi-Factory TEST** → **Run workflow**.
Select branch `feat/reusable-multifactory-framework-v1`.
Select action `framework-stage-controller`, factory `lab-warehouse`,
gateway `warehouse-main`, project `FactoryASmoke`.

The action now delegates through `deploy-test.yml` →
`reusable-deploy.yml` → `scripts/manual_factory_dispatch.py` →
`scripts/factory_a_controller_smoke.py`. It validates the selected factory/
Gateway/project and releases only to the local isolated EAM TEST Controller.

The stage adapter backs up project directories from both LAB containers,
stages an update or confirms unchanged files, compares SHA-256, and scans the
Controller. Project archives are not complete Gateway disaster-recovery backups.

**No EAM Agent Task is created or executed by this staging path.**
`FactoryASmoke` on Controller is separate from remote EAM Agent deployment.
Factory B is intentionally validation-only until its TEST Controller and
credentials are independently commissioned.

The new `deploy-test.yml` and `reusable-deploy.yml` are callable workflows,
not stand-alone `workflow_dispatch` entries. A new manual workflow filename
on a feature branch is not normally dispatchable until present on the default
branch. Hence use the registered legacy manual workflow selecting the feature
branch.

## Status

The underlying Factory A stage adapter passed a real update in GitHub run
41504512471. The V3 manual nested-call path must be verified by an actual
`workflow_dispatch` run before declaring that route fully proven.

Production HOLD. Test Gateway real PLC/OPC UA/FAT separately.
