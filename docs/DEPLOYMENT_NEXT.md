# Reusable TEST deployment: staged milestone

The repository's old scripts/deploy_test.py assumes direct host access to Docker named volumes and an EAM Gateway Timer script that is not installed. **Do not use it.**

The new GitHub workflow:
- PR/push: validation ONLY.
- Manual Run workflow -> action=validate: validation ONLY.
- Manual Run workflow -> action=stage-controller: runs on approved ARM64 self-hosted runner, validates allowlisted Controller/Agent containers, backs up Controller project directory, stages new project (CREATE ONLY), verifies copied file hashes and uploads evidence.
- NEVER invokes EAM automatically and NEVER declares E2E PASS.
- Requires Environment `ignition-test` and variables:
  - `IGNITION_CONTROLLER_CONTAINER=ignition-eam-controller`
  - `IGNITION_AGENT_CONTAINER=ignition-eam-agent`
  - `IGNITION_BACKUP_DIR=/home/tomha/ignition-eam-backups` (pre-create this private directory on runner host)

## After stage

1. On Controller 9188, press Platform -> System -> Projects -> Scan File System.
2. Confirm DeploymentSmokeTest appears and Perspective Main renders in actual Designer; hand-authored file-based source is a candidate, not known-good Gateway export.
3. Take a Gateway .gwbk backup of Controller and Agent before EAM Send Project.
4. Create EAM Send Project task: Local System -> DeploymentSmokeTest -> connected EAM-Agent only. Execute in lab.
5. Check EAM task result, project on Agent 9288, and Perspective page renders the exact expected label. Only then document FAT evidence.
6. A full automatic end-to-end workflow still requires authenticated Gateway scan/runtime attestation, supported EAM invocation with task-completion verification, and browser-level Perspective smoke test.

## Security

The self-hosted runner can invoke Docker commands, effectively a privileged host capability. Do not run untrusted PR code on it. Stage is restricted to explicit manual dispatch on main, but malicious changes merged into main remain a supply-chain risk. Use protected branches, approved maintainers and a dedicated disposable runner for deployments.
