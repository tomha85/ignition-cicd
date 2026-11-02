# Multi-factory Ignition CI/CD architecture

This V3 layout uses `framework/`, `factories/`, `shared/`, `tests/`, and `.github/workflows/`. Existing validated factory identifiers are `lab-warehouse` (Factory A demo) and `lab-assembly` (Factory B demo); changing identifiers requires a separately verified migration of manifests and deployment targets. See [detailed architecture](ARCHITECTURE_V2.md).

Ignition native project resources remain in `factories/<factory-id>/projects/<project>/`. During migration, certain files are mirrored under `ignition-project/` and CI requires byte parity. No Agent task invocation or production promotion is implied by staging a Controller.
