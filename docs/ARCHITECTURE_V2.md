# Ignition 8.3 multi-factory repository architecture V2

Status: FEATURE-BRANCH CANDIDATE. Agent EAM transfer and production NOT QUALIFIED.

## Layout

- framework/: shared deterministic source/Gateway/environment checks and fail-closed adapters.
- factories/<factory-id>/factory.json: equipment/project/Gateway identity and planned targets.
- factories/<factory-id>/projects/: canonical native Ignition 8.3 project trees for NEW framework.
- factories/<factory-id>/gateways/<gateway-id>/config/: curated Gateway metadata and approved exports.
- factories/<factory-id>/environments/: separate development, TEST and production target declarations.
- targets/lab-targets.json: explicit reviewed target registry; only FactoryASmoke Controller stage is approved.
- compatibility/legacy-source-mirrors.json: exact source-parity gate for retained legacy paths.
- shared/schemas/: JSON Schema 2020-12 contracts; shared/templates and project-resources are optional.
- examples/: simple/complex onboarding instructions, not fabricated PLC project resources.
- tests/: old regression suite plus new source-drift/configuration/authorization tests.
- .github/workflows/: old deployment workflows stay intact, new architecture CI is read-only.

## The migration source-of-truth rule

Legacy workflows on main still consume ignition-project/*. The new framework reads
factories/<factory-id>/projects/*. For project pairs listed in compatibility/
legacy-source-mirrors.json, both copies MUST have exactly identical files and
hashes. A changed project must update both in the same reviewed commit until
all old workflow consumers are migrated. Do not delete the old paths today.
FactoryASmoke is factory-owned and does not have a legacy mirror.

## Why this is still a candidate

Gateway configuration resources=[] means NOT PROVIDED, not that real plants
have no tags, PLC devices, alarms or database dependencies. The source layer
does not invent device mapping or process values. Only the static LAB projects
and the Factory A Controller smoke have evidence. Generic Send Project to Agent,
Perspective browser rendering, fault/recovery drills, physical PLC/OPC mapping
and production authorization remain HOLD.

## Run tests

python framework/cli/check_repo.py
python -m unittest discover -s tests -v
python scripts/reusable_factory.py --check-catalog

Architecture CI executes on GitHub-hosted Python 3.12 and 3.13 runners;
it does not access a Gateway or any OT network.

## Governance

CODEOWNERS documents ownership, but DOES NOT enforce review until repository
branch protection/rulesets and required CI checks are configured in GitHub.
Before customer use, migrate to private customer repositories and a versioned
shared framework with scoped secrets, approvals, and separately commissioned
EAM agents and target registries.
