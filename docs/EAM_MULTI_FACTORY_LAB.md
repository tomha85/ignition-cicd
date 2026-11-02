# EAM Multi-Factory TEST Deployment — commissioning status

Existing `.github/workflows/ignition-e2e.yml` (Direct GitOps) is **unchanged**.
New workflow: `ignition-eam-multi-factory.yml`.

## Three independent native Perspective projects

| TEST factory | GitHub source | required EAM Agent | Send Project task | runner-side TEST container |
| --- | --- | --- | --- | --- |
| factory_a | ignition-project/WarehouseHMI | EAM-Factory-A | CICD-SEND-WarehouseHMI-A | ignition-factory-a-test |
| factory_b | ignition-project/ConveyorHMI | EAM-Factory-B | CICD-SEND-ConveyorHMI-B | ignition-factory-b-test |
| factory_c | ignition-project/PackagingHMI | EAM-Factory-C | CICD-SEND-PackagingHMI-C | ignition-factory-c-test |

Agent names and Docker container names above are **planned test targets**, not evidence that the containers or Gateway Network connections exist.

## Validate (works without a live EAM Controller)

```bash
gh workflow run ignition-eam-multi-factory.yml --repo tomha85/ignition-cicd --ref main -f action=validate -f factory=factory_a
```

## Live deploy prerequisites (NOT YET COMMISSIONED)

1. Provision three independent TEST Ignition 8.3 Gateways and EAM modules, plus a TEST Controller. Do not reuse production Gateway or PLC.
2. Configure Agent Gateway Network connections and the three EAM Send Project tasks. Verify each task actually sends the corresponding project to the corresponding TEST Agent.
3. Install a Controller-only, authenticated, allowlisted native EAM automation bridge and verify an EAM task **invocation receipt**, followed by independent Agent project SHA256 checks. The provided `controller/eam_multi_factory_gateway_timer.py` is a Controller-only gateway timer source template; it must be installed and verified within the actual Gateway scripting configuration. `system.eam.runTask()` does not itself certify remote completion.
4. Configure the self-hosted `ignition-lab` runner with TEST Docker access and GitHub environment `ignition-test` vars: `IGNITION_CONTROLLER_CONTAINER=ignition-eam-controller`, `IGNITION_FACTORY_A_CONTAINER=ignition-factory-a-test`, `IGNITION_FACTORY_B_CONTAINER=ignition-factory-b-test`, `IGNITION_FACTORY_C_CONTAINER=ignition-factory-c-test`, `IGNITION_BACKUP_DIR` pointing to an existing directory outside source checkout. Only after validating the native bridge, set `IGNITION_EAM_BRIDGE_COMMISSIONED=YES`.
5. For an approved TEST-only deployment, run `action=deploy-test`. The current adapter requires the bridge to write a completion receipt at `/usr/local/bin/ignition/data/eam-multi-factory-requests/invoked-<request_id>.json` containing `request_id`, `eam_task`, `task_invoked: true`. This confirms invocation only; remote deployment PASS requires independent Agent file verification.
6. Each run backs up Controller and selected Agent project directories before mutation; verifies staged content; requests the task; verifies target file SHA256. **It does not prove Perspective browser rendering, real PLC mapping, or recovery correctness.**

**SAFETY:** Until bridge commissioning and 3-Gateway live integration tests pass, `deploy-test` is intentionally HOLD. Do not treat CI PASS or release plan generation as actual remote deployment. Never promote to production using this workflow.
