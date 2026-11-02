# Registered isolated TEST targets

`lab-targets.json` is the authority for approved LAB TEST **Controller staging**.
The authoritative `factory.json` describes which projects belong to which
Gateway. Neither a user-supplied project name nor a factory manifest alone
grants deployment authority.

An approved target must provide a matching factory/Gateway TEST target ID,
`controller_stage_approved: true`, `project_scope: all_manifest_projects`,
a reviewed local Controller and Agent container ID, and an HTTPS **loopback**
Controller scan endpoint. The generic staging adapter revalidates these fields
and the immutable source SHA **after GitHub's Required Reviewer approval**.

Currently `lab-warehouse/warehouse-main` is commissioned for local Controller
staging; **all registered native projects on this Gateway** (`WarehouseHMI`,
`FactoryASmoke`) may be staged. No project names are embedded in the
generic deployment engine.

Factory B/C remain validate-only because their Controller targets have not
been independently commissioned. Do not invent Controller addresses, Agent
registrations or production endpoints to enable them.

Staging always takes verified project directory archives before Controller
writes, compares source resources and requests the Controller scan. These
archives are **not** full Gateway backups. Successful LAB Controller staging
does not prove Perspective browser runtime, Agent EAM delivery, PLC mappings,
FAT, or authorize production. EAM Agent tasks and production stay HOLD.
