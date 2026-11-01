# Ignition EAM test lab

This is a lab-only pipeline starter, not a qualified end-to-end deployment. Use real Ignition 8.3 file-based project resources.

1. Create separate Ignition 8.3 DEV/Controller and TEST/Agent Gateways; install/trial EAM; configure Gateway Network trust.
2. Create a minimal Perspective project **DeploymentSmokeTest**, with a static label (V1 then V2); copy its genuine file-based project directory to ignition-project/DeploymentSmokeTest.
3. On Controller, configure an EAM Send Project task named **Lab_Send_Project**, source Local System, project DeploymentSmokeTest, target TEST Agent only. Save a Gateway backup before mutations.
4. Install the controller/eam_trigger_gateway_timer.py logic in a separate Controller-only management project. Do not distribute it with EAM.
5. GitHub Actions: attach a self-hosted Linux runner with label ignition-lab, create Environment ignition-test, and define variables CONTROLLER_PROJECTS_DIR, AGENT_PROJECTS_DIR, CONTROLLER_TRIGGER_DIR, DEPLOY_BACKUP_DIR. They must refer to distinct, authorized **TEST ONLY** paths visible to the runner.
6. **REQUIRED BEFORE DEPLOYMENT:** Implement and validate a real Controller project scan and runtime version gate (see controller/REQUIRED_SCAN_GATE.md). Current implementation does not safely establish this.
7. Open PR, run validation, merge to main; deploy job stages and triggers test-only EAM task. Compare actual project contents on Agent and confirm Perspective renders correct version independently.
8. Fail closed if source project is missing, EAM task is not started, hashes differ, or Perspective runtime was not independently tested.

Notes: no passwords, PLC mappings or production data in repo; no direct GitHub-hosted runner access to OT Gateway; never treat CI success as FAT pass. EAM project transfer does not automatically include tags/UDTs or Gateway-level device/DB connections.
