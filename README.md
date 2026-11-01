# Ignition GitHub → EAM deployment lab

This repository contains a reusable **Ignition 8.3 TEST-only** CI/CD starter: developer changes → pull request → merge main → GitHub Actions → EAM Controller → TEST Agent verification.

**Status: engineering starter, NOT a qualified end-to-end deployment.** The actual file-based Ignition `DeploymentSmokeTest` project and the Controller/Agent trial Gateways must still be configured and tested.

- CI intentionally **fails closed** if a genuine `ignition-project/DeploymentSmokeTest/project.json` and additional project resources are absent.
- GitHub Actions deployment requires a self-hosted runner with `ignition-lab` label, an `ignition-test` environment, correct lab-only paths, and an explicitly configured EAM task.
- Do not point at production Gateways. Always back up before changes.

See `docs/LAB_README.md` for lab setup and `controller/REQUIRED_SCAN_GATE.md` for the missing Controller scan/verify step. Older package examples are under `reference/initial-starter/`.
