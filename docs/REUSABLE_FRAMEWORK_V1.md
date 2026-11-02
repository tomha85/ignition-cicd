# Ignition reusable multi-factory framework V1 — isolated candidate

**Branch only:** feat/reusable-multifactory-framework-v1

**Preserved baseline:** main at 7627fb70d201cd06c7736a0e6b4d89382f47be35

**Backup branch:** backup/main-20261102-before-framework-v1

This first iteration adds an isolated, zero-external-dependency **read-only**
manifest validation and release-planning framework. It DOES NOT replace any
existing Direct TEST or EAM workflow and DOES NOT deploy to a Gateway.

## Tested design boundaries

- Existing native Ignition projects, old scripts, manifests and CI workflows remain byte-unchanged.
- The new engine discovers factory folders dynamically. No factory or Gateway is
  hard-coded in reusable_cicd/.
- Each factory owns its project tree: factories/<factory-id>/projects/<project>.
  This prevents ../../ traversal or accidentally importing another factory's files.
- Each Gateway may have any number of project entries; a factory may define
  multiple Gateways and independently configured environments.
- Only secret **names** (e.g. IGNITION_EAM_API_TOKEN) appear in Git.
  Never commit secrets, OT addresses or live credentials.
- No production deployments: every example is deployment_enabled=false;
  production additionally requires approval_required=true.
- SHA256 checks reflect source file content, but not Gateway runtime correctness.
- The example project snapshots were copied from the existing static smoke projects.
  They do not imply real PLC, OPC UA or physical FAT qualification.

## Local validation

Run from repo root:

    python -m unittest discover -s tests -v
    python scripts/reusable_factory.py --check-catalog
    python scripts/reusable_factory.py --factory lab-warehouse
    python scripts/reusable_factory.py --factory lab-warehouse \
      --gateway warehouse-main --environment test \
      --sha 7627fb70d201cd06c7736a0e6b4d89382f47be35

Expected release plan: status VALIDATED_NOT_DEPLOYED; no EAM invocation,
no Gateway connection, browser_render NOT_TESTED, fat NOT_TESTED.

## Add another factory

1. Create factories/<new-factory-id>/factory.json and
   factories/<new-factory-id>/projects/<native-project-name>/ .
2. Use real Ignition 8.3 project files, including project.json and
   resource.json descriptors. Do not invent PLC tags or physical bindings.
3. Assign distinct github_environment and target_id per environment;
   use secret_refs as names, never values.
4. Keep deployment_enabled=false. Run --check-catalog and all tests.
5. For a real customer, use a **private customer repository** consuming a
   separately versioned shared workflow/engine. Never combine unrelated
   clients' sources, access or credentials in a public repository.

## Roadmap for integration (NOT DONE)

- Support customer-private repos, versioned reusable workflow and signed packages.
- Add a reviewed Designer-to-worktree sync for Linux/Windows with pre-change backup.
- Add a fully tested, environment-allowlisted EAM adapter (separate from this harness).
- Run live isolated TEST Gateway project scans and actual browser-render tests.
- Add tag provenance, alarm, simulator/FAT, recovery drills and reviewed production gates.

The legacy paths .github/workflows/ignition-e2e.yml and
.github/workflows/ignition-eam-multi-factory.yml are unchanged. A green hosted
CI run demonstrates validation only, never a live deployment.
