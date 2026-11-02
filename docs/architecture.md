# Ignition 8.3 multi-factory GitHub repository — standard V3

This is a **real feature-branch layout**, not a claim of Agent or production
qualification. Root directories include:

```text
ignition-cicd/
├── .github/
│   ├── workflows/
│   │   ├── validate.yml
│   │   ├── build-release.yml
│   │   ├── deploy-test.yml
│   │   └── reusable-deploy.yml
│   └── CODEOWNERS
├── framework/
│   ├── cli/
│   ├── validation/       # manifest.py, projects.py, gateway_config.py
│   ├── adapters/         # ignition_83.py, eam.py, docker_lab.py
│   ├── deployment/       # planner, backup, stage, deploy, verify, recovery
│   └── security/         # policies.py
├── factories/
│   ├── lab-warehouse/    # Factory A demo, Gateway warehouse-main
│   │   ├── factory.json
│   │   ├── projects/     # WarehouseHMI, FactoryASmoke
│   │   ├── gateways/
│   │   ├── environments/
│   │   └── tests/
│   └── lab-assembly/     # Factory B demo, Gateways assembly-main/utilities-main
│       ├── factory.json
│       ├── projects/
│       ├── gateways/
│       ├── environments/
│       └── tests/
│   └── lab-packaging/    # Factory C, one Gateway, PackagingLineHMI
│       ├── factory.json
│       ├── projects/
│       ├── gateways/
│       ├── environments/
│       └── tests/
├── shared/               # project-resources, templates, schemas
├── tests/                # unit, integration, gateway, fat
├── examples/             # simple-factory, complex-factory
├── docs/
└── README.md
```

See [the 3-factory showcase](THREE_FACTORY_SHOWCASE.md) for example projects, Gateway assignments and commands.

The V3 interfaces in `framework/validation/` delegate to the
previously regression-tested engine at `reusable_cicd/core.py` rather than
duplicating validators. The factory-owned project files remain authoritative
for the new pipeline; legacy `ignition-project/` mirrors are retained
temporarily, with byte-level source parity CI.

A `factory.json` declares approved source project membership and environment
target references. It does not grant automatic access to a real factory.
A target needs an independently commissioned LAB adapter, backup and approval.
Only Factory A's TEST Controller stage has such an adapter. A successful
Controller scan is not EAM Send Project to an Agent.

Names `factory-a` and `factory-b` in early sketches were placeholders;
keeping `lab-warehouse` and `lab-assembly` as identifiers avoids
silently changing existing site/target mappings. Gateway resource metadata is
not a substitute for real PLC tags, alarm configuration or verification.

See [the original detailed architecture](ARCHITECTURE_V2.md) and
[deployment guide](deployment-guide.md).
