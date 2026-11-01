# DeploymentSmokeTest — candidate native Perspective project

This directory contains a minimal, **hand-assembled Ignition 8.3 file-based project candidate** (not an export from a running Gateway). It is intended for the isolated EAM TEST lab only.

- Project: `DeploymentSmokeTest`
- View: `Main`
- Screen labels: `IGNITION EAM CI/CD SMOKE TEST`, `SMOKE VERSION V1`.
- No tags, UDTs, OPC/PLC writes, external databases or secrets.
- The static resource validator checks JSON and file layout only. It **cannot certify Gateway acceptance**.
- Before declaring a full deployment PASS, load the project into an actual Ignition 8.3 test Gateway, inspect it in Designer, and verify that the Perspective page renders. If the Gateway rewrites metadata, commit the **Gateway-generated** files back as the authoritative project baseline.

# E2E release gate

Do not use automated file staging → EAM until the Controller project scan and runtime identity check described in `controller/REQUIRED_SCAN_GATE.md` has been implemented. A successful resource hash comparison on the Agent does not prove a Perspective session renders.
