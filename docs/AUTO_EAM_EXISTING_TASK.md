# Automatically run an existing EAM Send Project task (isolated TEST)

The two-job workflow `.github/workflows/ignition-eam-multi-factory.yml`
now has an **optional automatic EAM step within Job 2**, immediately after
approved TEST Controller staging. It does NOT create or overwrite EAM tasks,
change PLCs, provision connections, or deploy to production.

## Status: safe by default — not commissioned

The registered `lab-warehouse` target has `eam_send_commissioned: false`.
The existing project binding proposed for review is:

- Factory: `lab-warehouse`
- Gateway: `warehouse-main`
- Project: `WarehouseHMI`
- Existing EAM task name: `CICD-SEND-WarehouseHMI-A`
- Expected EAM Agent name: `EAM-Agent`

**This name comes from the existing LAB manifest, not a live verification of the
Controller task.** Never flip the commissioning flag based on a name alone.

## One-time commissioning checklist

1. Confirm `ignition-eam-controller` and `ignition-eam-agent` both run in the
   isolated TEST Docker LAB on the self-hosted `ignition-lab` runner.
2. On Ignition Controller, inspect the existing task under
   **Enterprise → Agent Tasks**. Verify task type **Send Project**, source
   `WarehouseHMI` on **Local System**, exactly one target named
   `EAM-Agent`, and task enabled/not suspended. Verify the Agent is connected.
3. Confirm your Ignition 8.3 Controller API supports the `find` resource and
   `force/{owner}/{name}` endpoint in its local **OpenAPI**. Grant an API
   key the minimum read/invoke privileges needed. Store it in
   `ignition-test` Environment secret `IGNITION_GATEWAY_API_TOKEN`.
   Do **not** copy credentials or tokens into Git.
4. Verify Controller CA file (runner path set by
   `IGNITION_CONTROLLER_CA_FILE`), backup directory, and a recoverable
   Agent backup. Ensure the TEST Agent project may safely be replaced.
5. Have a reviewer approve the change to
   `targets/lab-targets.json` setting `eam_send_commissioned: true` **only
   for the independently verified TEST target and binding**. The registry
   validator denies commissioning without an approved Controller stage
   and a unique, well-formed project/task/Agent binding.
6. Set the GitHub **Environment variable**, scoped to `ignition-test`:
   `IGNITION_EAM_AUTO_SEND_ENABLED=YES`. Do this only after the above
   checks pass.

## Running it

GitHub Actions → `Ignition EAM - Select Factory & Project (TEST)` →
`Run workflow` on `main` → Factory `lab-warehouse` →
Project `WarehouseHMI` → approve `ignition-test` deployment.

The Stage job will: verify approval → back up Controller and Agent project
trees → stage stamped native project → check hashes and Controller scan →
read existing EAM task configuration → confirm exact project, Agent, and
Controller API owner → invoke the task **once** through native EAM API →
verify target Agent Description and Perspective Main view/page resources.

The same workflow continues to stage other projects and factories without
running EAM if their target has not been commissioned. No task is invented.
Task invocation acceptance does **not** prove a Perspective page rendered or
physical PLC correctness. Actual completion needs Agent-side verification.
If the task was invoked but timed out, investigate EAM task history before
manually retrying; do not auto-retry and risk duplicate operations.

## Evidence and rollback

Controller staging evidence: `evidence/selected-controller-stage.json`.
EAM evidence: `evidence/selected-agent-eam.json`. Both are uploaded
even if the EAM step fails. `AGENT_RESOURCES_VERIFIED_NOT_BROWSER_TESTED`
means resource checks passed, **not** end-to-end runtime/FAT PASS.

Existing Controller pre-send backups remain available. Because EAM Send
Project may already have modified the Agent, a failed EAM step deliberately
does **not** trigger a blind rollback or automatic retry. Engineering review
and a separately verified recovery plan are required.
