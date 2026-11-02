# Legacy project compatibility during migration

Native project resources under factories/<factory-id>/projects are the canonical
source for the NEW manifest-driven framework. The existing workflows on main
still consume ignition-project/. To prevent conflicting releases, the explicit
legacy-source-mirrors.json registry must be byte-identical in CI.

Do not edit one mirrored location without synchronizing the other as part
of the same reviewed commit. After all legacy workflows are migrated, remove
only the truly unused mirror files in a SEPARATE reviewed PR with backups.
Do not delete old project trees while older LAB pipelines depend on them.
