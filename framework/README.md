# Reusable Ignition 8.3 engineering CI/CD framework

The framework namespace is the modular V2 architecture candidate.
Native project validation, versioned source parity, environment/Gateway configuration
metadata validation and the deny-by-default target registry are implemented.

The existing reusable_cicd V1 engine and all legacy deployment scripts are retained.
Nothing under framework starts an EAM Send Project operation or production deploy.
Controller staging remains limited to the previously audited FactoryASmoke lab adapter.

Run: python framework/cli/check_repo.py
Run: python -m unittest discover -s tests -v

Source-of-truth: factory projects under factories/<id>/projects/
Legacy copies under ignition-project/ remain frozen compatibility mirrors
until existing workflow consumers have been migrated. Byte parity is checked in CI.

NO physical PLC mapping, OPC UA target, EAM Agent PASS or browser rendering is inferred.
