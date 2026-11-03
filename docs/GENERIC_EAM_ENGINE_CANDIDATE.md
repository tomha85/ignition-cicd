# Generic Multi-Factory EAM Engine V1 — isolated design candidate

**STATUS: READ-ONLY / NOT DEPLOYED.** The original, working `main` LAB
workflow, approval, task invocation, and runner are completely unchanged.
No production authorization, Gateway writes, task execution, connection
provisioning, or OT network calls are made by this candidate.

## Goal

One reusable engine for multiple factories. A factory brings native Ignition
source and verified topology; each TEST target declares:

- factory, gateway and TEST target identifiers;
- scoped runner labels (a generic engine must not assume all targets run on one laptop);
- Controller API HTTPS endpoint and reference names for the token and CA;
- EAM Agent identity and per-project pre-existing EAM Send Project task;
- a named approval environment and deployment_enabled=false.

Source of truth for the candidate: `generic-eam/targets.json`.
The real source manifests remain in `factories/<factory>/factory.json`.
No secrets, PLC IPs or invented runtime endpoints should be committed to the
public repository. Only the existing TEST LAB localhost configuration is
included; other factory endpoints used by tests are explicitly fictitious.

## Safe execution

From this branch:
```bash
python scripts/plan_generic_eam.py --factory lab-warehouse --project WarehouseHMI
python -m unittest discover -s tests -p 'test_generic_eam_candidate.py' -v
```

GitHub Actions: `Candidate - Generic Multi-Factory EAM Plan (NO DEPLOY)`.
The PR automatically tests the resolver. Manual dispatch on the branch
can output a plan. This workflow never runs on a privileged self-hosted runner.

## Proof standards

- Resolves Warehouse TEST config without invoking any EAM endpoint.
- An independent simulated Packaging TEST config reuses the same resolver,
  yielding a different runner, Agent, endpoint and task.
- Rejects wrong factory, ambiguous project mappings, missing tasks, duplicate
  targets, wrong Gateway, insecure endpoints, inline credentials and production.
- All returned plans include `deployment_authorized=false`.
- GitHub CI green means deterministic offline plan PASS **only**.

## Next phase: do not conflate design with live deployment

A separate deployment adapter must use the validated plan only after
per-factory installation and review of a trusted runner, API permissions,
Gateway Network/EAM health, full backup recovery, approved exact task and
independent target runtime verification. It must prevent a target config from
supplying arbitrary runner labels or endpoints without an independent
allowlist. The deployed release must be immutable and the current-run
Engineer approval mandatory. Do not toggle `deployment_enabled` in this
candidate or replace the working LAB pipeline.

The user-proven original pipeline on `main` stays the rollback reference.
