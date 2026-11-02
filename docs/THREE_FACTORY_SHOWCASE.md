# Three-factory showcase — Ignition 8.3 CI/CD

This repository demonstrates **one shared CI/CD framework** serving three separate customer-style plants. All factory names and projects here are examples; no physical PLC mapping is asserted.

| Example | Factory ID | Gateways | Native Ignition projects | Real deployment evidence |
| --- | --- | --- | --- | --- |
| **Factory A — Warehouse** | `lab-warehouse` | `warehouse-main` | `WarehouseHMI`, `FactoryASmoke` | `FactoryASmoke` updated on isolated TEST **EAM Controller** |
| **Factory B — Assembly** | `lab-assembly` | `assembly-main`, `utilities-main` | `ConveyorHMI`, `PackagingHMI` | Validate/build only; target Gateways not commissioned |
| **Factory C — Small Packaging** | `lab-packaging` | `packaging-main` | `PackagingLineHMI` | Validate/build only; intentionally no Agent |

## What the repository looks like

```text
ignition-cicd/
├── .github/workflows/             # Same validation/build/Controller staging engine
├── framework/                     # Engineering validation, security and deploy adapters
├── factories/
│   ├── lab-warehouse/             # Factory A: one Gateway, two projects
│   │   ├── factory.json
│   │   ├── projects/
│   │   │   ├── WarehouseHMI/
│   │   │   └── FactoryASmoke/
│   │   ├── gateways/warehouse-main/config/gateway.json
│   │   ├── environments/{dev,test,production}.json
│   │   └── tests/requirements.json
│   ├── lab-assembly/              # Factory B: two Gateways
│   │   ├── factory.json
│   │   ├── projects/
│   │   │   ├── ConveyorHMI/
│   │   │   └── PackagingHMI/
│   │   ├── gateways/
│   │   │   ├── assembly-main/config/gateway.json
│   │   │   └── utilities-main/config/gateway.json
│   │   ├── environments/{dev,test,production}.json
│   │   └── tests/requirements.json
│   └── lab-packaging/             # Factory C: one Gateway, one project
│       ├── factory.json
│       ├── README.md
│       ├── projects/PackagingLineHMI/
│       ├── gateways/packaging-main/config/gateway.json
│       ├── environments/{dev,test,production}.json
│       └── tests/requirements.json
├── shared/{schemas,templates,project-resources}/
├── tests/{unit,integration,gateway,fat}/
├── examples/{simple-factory,complex-factory,small-packaging}/
└── docs/
```

Every `projects/<ProjectName>/` contains native Ignition resources, including `project.json`, `com.inductiveautomation.perspective/page-config/`, and `com.inductiveautomation.perspective/views/Main/resource.json` plus `view.json`.

## See how different factories are selected

All three choices appear in the **Standard V3 Build Immutable Native Ignition Source Release** workflow. For Factory C use `lab-packaging` / `packaging-main` / `PackagingLineHMI`. For Factory B use `lab-assembly` / `assembly-main` / `ConveyorHMI`. For Factory A use `lab-warehouse` / `warehouse-main` / `FactoryASmoke`.

### Local read-only validation (no Gateway credentials required)

```bash
python framework/cli/check_repo.py

python framework/cli/validate_factory.py --factory lab-warehouse --gateway warehouse-main --project FactoryASmoke --sha "$(git rev-parse HEAD)"
python framework/cli/validate_factory.py --factory lab-assembly --gateway assembly-main --project ConveyorHMI --sha "$(git rev-parse HEAD)"
python framework/cli/validate_factory.py --factory lab-packaging --gateway packaging-main --project PackagingLineHMI --sha "$(git rev-parse HEAD)"

python -m unittest discover -s tests -v
```

### Build a project release ZIP (does not deploy)

```bash
python scripts/build_release_v3.py \
  --factory lab-packaging --gateway packaging-main \
  --project PackagingLineHMI --sha "$(git rev-parse HEAD)" \
  --output /tmp/packaging-source-release.zip
```

Source validation and ZIP package PASS **do not** prove Perspective browser rendering, OPC UA/PLC connections or functional FAT.

## Approving Factory A staging

After **Validate PASS**, GitHub should show **Review deployments** for the
`ignition-test` Environment. Only an approval by `tomha85` allows the stage
job to run. Follow [the approval setup guide](APPROVAL_WORKFLOW.md) before
testing. Without a configured reviewer, the independent stage guard produces
HOLD and does not modify the Controller.

## Scope of stage/deploy

- Only Factory A / `FactoryASmoke` has a TEST Controller staging adapter qualified through the existing LAB smoke workflow.
- Factory B and C **must fail closed** for `framework-stage-controller` until independently commissioned, backed up and reviewed.
- The user will manage EAM **Agent tasks** separately, after Controller staging.
- All production release remains HOLD.

## Why does `ignition-project/` still exist?

The canonical **new** per-factory projects are under `factories/<factory-id>/projects/`. The older root `ignition-project/` remains temporarily because legacy CI/CD and `DeploymentSmokeTest` scripts still consume those paths. It is not a second recommended location for new development. Byte-for-byte checks prevent known mirrored resources from drifting. Remove the old tree only in a separate migration after legacy consumers have been updated and retested.
