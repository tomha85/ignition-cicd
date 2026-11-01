# Earlier ZIP export-based starter (reference only)

This is the original lab candidate for manually exporting an Ignition project and packaging it into a release ZIP. It is separate from the primary `.github/workflows/ignition-e2e.yml` used by this repository.

The reference is NOT a second active GitHub Actions workflow. No real Ignition project export is included. Run with `python3 reference/initial-starter/scripts/package_release.py` if desired, after placing a genuine export at `reference/initial-starter/exports/ManufacturingSCADA.zip`.

This approach only validates and packages a release: it does not deploy through EAM or prove an Ignition Gateway FAT.
