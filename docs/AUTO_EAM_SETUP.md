# Ignition TEST EAM automation: opt-in candidate

**NOT production ready.** No automatic production deploy. A successful task invocation and matching files do not prove EAM task success or browser Perspective runtime. The script remains fail-closed.

## One-time setup

1. On Controller `http://localhost:9188`, create an Ignition 8.3 API Key with least permissions required for project scan (Platform > Security > API Keys). Consult `http://localhost:9188/openapi` for POST `/data/api/v1/scan/projects`, including required roles/permissions. Store token as GitHub Environment secret `IGNITION_GATEWAY_API_TOKEN` under `ignition-test`. Do not share token or print it.
2. On Controller, make an isolated management project (e.g. `EAMLabManagement`) with Gateway Timer Script copied from `controller/eam_trigger_gateway_timer.py`. Fixed Delay 1000 ms, Dedicated thread. This management project MUST NOT be sent to the Agent and requires manual review of script capabilities. The script invokes the preconfigured **available/on-demand** task `Lab_Send_Project` for one authorized connected Agent only. Confirm task is callable on demand.
3. GitHub Environment variables (existing): `IGNITION_CONTROLLER_CONTAINER`, `IGNITION_AGENT_CONTAINER`, `IGNITION_BACKUP_DIR`.
4. Additional gate: `IGNITION_CONTROLLER_RUNTIME_VERIFIED_SHA` must equal the exact commit SHA. This manual attestation is a safety hold until an independent Gateway runtime SHA verification endpoint exists. Setting it alone does not prove correctness; only set after actual Controller validation. If missing, job stages+scans then exits HOLD without triggering EAM.
5. Prefer a dedicated, trusted runner. Docker daemon access is effectively host administrator access. Do not route untrusted PR code to the self-hosted runner.

## Run

Workflow Actions -> Ignition EAM E2E TEST -> Run workflow -> main -> `deploy-eam`.

The workflow: backup Controller and Agent project directories -> update exact allowed Controller project -> POST scan/projects -> require separate Controller runtime SHA attestation -> request isolated EAM trigger -> wait for invocation receipt -> compare Agent file hashes against Git release.

Uploaded `evidence/auto-eam.json` is **RESOURCE_TRANSFER_VERIFIED** at most; full E2E remains HOLD until EAM task history and browser-rendered Perspective checks are independently proven. For V2, change visible version, verify Controller, then attest exact commit SHA. A secure source-controlled runner project should not contain tokens.

## Caution

`scripts/auto_eam_lab.py` changes Controller project files and creates backups. Requires user-approved one-time Gateway setup and manual runtime gate. Do not run until backup retention, timer script, and credentials are reviewed. Repeated runs may encounter a retained `.ci-prior-SHA` directory; inspect rather than deleting automatically.
