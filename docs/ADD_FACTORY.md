# Add a customer factory safely

1. Create factories/<factory-id>/factory.json; factory ID must be unique and
   use lowercase letters, numbers and hyphens.
2. Add Gateway IDs, exact native project names and project source paths.
3. Supply real Ignition 8.3 project.json and resource.json files unchanged under
   factories/<factory-id>/projects/<ProjectName>/.
4. For each Gateway create gateways/<gateway-id>/config/gateway.json.
   Start with resources=[] and deployment_enabled=false; add curated exports
   only after provenance/quality checks and site engineering review.
5. Add connections/gateways.json, connections/databases.json,
   connections/opcua.json, connections/plc-devices.json. Start all of them
   with NOT_PROVIDED and empty arrays, without inventing connection IPs.
   See FACTORY_CONNECTIONS.md for the strict source-only schema and examples.
6. Add environments/dev.json, test.json, production.json. All declared
   Gateway targets must match the authoritative factory.json exactly.
7. Add TEST target IDs to a reviewed target registry only after commissioning.
   A manifest alone never permits access to an OT target.
8. Keep credentials and real site connection details outside a public GitHub
   repository; use a private repository, secret manager and protected environments.
9. Define requirement and FAT evidence traceability separately. Never infer PLC
   mappings or physical behavior from static source files or simulation.
10. Run python framework/cli/check_repo.py and all unit/regression tests.
11. Keep EAM Agent/production deployment on HOLD until independent proofs exist.

When onboarding a Factory or Project, run
`python scripts/sync_workflow_choices.py` and commit the generated dropdown
options in the same PR. GitHub Actions native dropdowns cannot cascade by
Factory. Never permit arbitrary Docker targets or credentials in source files.

