# TEST deployment vs production boundaries

The existing EAM multi-factory TEST workflow on the feature branch supports
framework-validate for multiple factory definitions and framework-stage-controller
ONLY for lab-warehouse/warehouse-main/FactoryASmoke.

The Controller smoke backs up the two LAB project trees, stages a create-only
project or verifies byte-identical content, scans the TEST Controller using
trusted HTTPS, and records file hashes plus evidence. The project tree tarballs
are NOT verified complete Gateway backups.

Generic EAM Send Project to Agent is intentionally denied by framework/
deployment/deploy.py. Production rollback is also disabled. A Controller
scan status is not proof of Perspective browser rendering or Agent deploy.

Future approval requires: signed/pinned release, site-specific secrets and
Gateway/Agent identity, full Gateway backup and restore exercise, EAM task
invocation AND independent Agent hash comparison, Perspective behavioral FAT,
real-signal mapping provenance, approvals and documented recovery.

