# Add a customer factory safely

1. Create factories/<factory-id>/factory.json; factory ID must be unique and
   use lowercase letters, numbers and hyphens.
2. Add Gateway IDs, exact native project names and project source paths.
3. Supply real Ignition 8.3 project.json and resource.json files unchanged under
   factories/<factory-id>/projects/<ProjectName>/.
4. For each Gateway create gateways/<gateway-id>/config/gateway.json.
   Start with resources=[] and deployment_enabled=false; add curated exports
   only after provenance/quality checks and site engineering review.
5. Add environments/dev.json, test.json, production.json. All declared
   Gateway targets must match the authoritative factory.json exactly.
6. Add TEST target IDs to a reviewed target registry only after commissioning.
   A manifest alone never permits access to an OT target.
7. Keep credentials and real site connection details outside a public GitHub
   repository; use a private repository, secret manager and protected environments.
8. Define requirement and FAT evidence traceability separately. Never infer PLC
   mappings or physical behavior from static source files or simulation.
9. Run python framework/cli/check_repo.py and all unit/regression tests.
10. Keep EAM Agent/production deployment on HOLD until independent proofs exist.

The GitHub manual workflow currently has a static factory choice dropdown.
Onboarded factories require a reviewed choice update, or a validated text
input with target-registration checks. Never permit arbitrary Docker targets.

