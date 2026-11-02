# Simple factory onboarding template

Start with a new private or internal factory identifier and one Gateway.
1. Add a native Ignition project under factories/<id>/projects/<title>/.
2. Add factory.json; set schema_version=1 and ignition_version=8.3.
3. Add gateways/<gateway>/config/gateway.json with resources=[] initially.
4. Add environments/dev.json, test.json, production.json.
5. No secret values or real PLC mappings in Git: use verified site inputs.
6. Add a TEST target only after engineering commissioning and review.
7. Run python framework/cli/check_repo.py and all Python regression tests.
8. EAM Agent transfer remains HOLD until an approved adapter is qualified.


Example: `factories/lab-packaging/` is a one-project source-only demonstration with deployment disabled.
