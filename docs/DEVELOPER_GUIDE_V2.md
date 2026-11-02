# Engineering workflow for native Ignition project source

Designer -> isolated DEV Gateway -> backup project and Gateway -> feature branch
-> update factory-owned native resource tree -> update registered legacy mirror
-> verify native resource identity and dependency metadata -> CI -> PR review
-> isolated Controller TEST stage -> separately commissioned EAM Agent deploy
-> browser/behavior/FAT evidence -> independent engineer production approval.

Maintain the original Perspective UI and resource paths. Linux/Windows
Designer-to-source syncing is not yet automated in this candidate. Any later
sync tool must implement conflict detection and backup-before-mutation.

Commands:
python framework/cli/check_repo.py
python -m unittest discover -s tests -v

Never edit main directly or treat synthetic test results as PLC mapping proof.

