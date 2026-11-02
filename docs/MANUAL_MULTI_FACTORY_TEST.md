# Manual multi-factory Ignition TEST workflow

## Current level of qualification

- The previous one-shot FactoryASmoke push succeeded on local TEST Controller.
- The new manual selector has unit/CI coverage, but it has **not yet completed a manual workflow_dispatch run**.
- Neither workflow performs EAM Send Project to Agent, browser rendering, OPC UA/PLC FAT or production deployment.
- PROJECTS backup is a project-tree archive only, not a qualified full Gateway disaster-recovery backup.

## Run manually from GitHub Actions (main remains unchanged)

1. Open the GitHub Actions tab of tomha85/ignition-cicd.
2. Open the **Ignition EAM - Multi-Factory TEST** workflow (this filename already exists on main).
3. Click **Run workflow**.
4. Under **Use workflow from**, choose **feat/reusable-multifactory-framework-v1**.
5. Set action to **framework-validate** (safe first test).
6. Set factory to **lab-warehouse**.
7. Set gateway_id to **warehouse-main**.
8. Set project_name to **FactoryASmoke**.
9. Click **Run workflow** and confirm the **Validate manually selected factory, Gateway and TEST project** job is green.

Test a different factory without any Gateway writes:

- action = framework-validate
- factory = lab-assembly
- gateway_id = assembly-main
- project_name = ConveyorHMI

Or use utilities-main + PackagingHMI. Native source validation for all
manifest-listed project types uses a common implementation.

## Approved Controller staging (TEST only)

After validation is green, launch another manual run with:

- branch = feat/reusable-multifactory-framework-v1
- action = framework-stage-controller
- factory = lab-warehouse
- gateway_id = warehouse-main
- project_name = FactoryASmoke

It selects the **existing**, explicitly commissioned LAB Controller smoke
adapter. On self-hosted runner [self-hosted, linux, ignition-lab], using
GitHub Environment ignition-test, it makes fresh archives of both project
directories, checks native SHA256, stages only if absent (or confirms exact
identity if already installed), and triggers the authenticated Controller
project scan. Evidence artifact: manual-factory-controller-evidence.

Any other factory, Gateway, or project combination for this stage action fails
closed with HOLD. This is intentional: other EAM Controllers and mappings are
not commissioned. The new manual action never runs production deployment or
automatically forwards to Agent.

## CLI alternative

    gh workflow run ignition-eam-multi-factory.yml \
      --repo tomha85/ignition-cicd \
      --ref feat/reusable-multifactory-framework-v1 \
      -f action=framework-validate \
      -f factory=lab-warehouse \
      -f gateway_id=warehouse-main \
      -f project_name=FactoryASmoke

To attempt the approved Controller-only stage after validation, replace the
action with framework-stage-controller.

## New factories

The framework discovers factory directories from factory.json. GitHub Actions
**choice** inputs are intentionally static; a newly onboarded factory should
be added to the dropdown by code review after its manifest passes tests.
No user-selected input may route directly to arbitrary containers or production.

Existing legacy actions validate, stage-controller and deploy-test, with
factory_a, factory_b and factory_c, remain unchanged on the feature branch.

## GitHub registration detail

GitHub requires workflow_dispatch workflow filenames to exist on default
branch. We extended the *already registered* EAM workflow file only on the
development branch. Always select that branch when using the new actions.
This preserves main's source/design and avoids registering any unsafe new
manual workflow on main.

## Interpretation

- VALIDATED_NOT_DEPLOYED = no Gateway changes
- CONTROLLER_STAGED_AND_SCANNED_NO_EAM = files present and Controller scan idle
- EAM_SEND_PROJECT=NOT_RUN = the Agent is NOT updated by this workflow
- Browser/FAT/production = NOT_TESTED / HOLD

Treat the new workflow as an isolated TEST candidate, not production-stable.
