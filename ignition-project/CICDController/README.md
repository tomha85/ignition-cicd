# CICDController (TEST Controller only)

This is an isolated Ignition 8.3 management project source scaffold. **It does not yet contain an installed/validated Gateway Timer resource.**

Ignition 8.3 Gateway Event scripts are project resources. Their on-disk layout must be exported from **the installed 8.3 Gateway** (with complete `resource.json` and Python data files) before claiming that a repository file is a runnable native timer. Do not copy this project to the EAM Agent.

Source of the intended Controller Gateway Timer: `controller/eam_trigger_gateway_timer.py`.

Before installation: create and verify a full .gwbk of Controller and Agent; confirm the EAM On-Demand Task exists, and confirm Gateway timer schema in a disposable isolated test project. Only after matching the exact native schema, add the corresponding timer resources under this project, stage it to Controller, scan with trusted HTTPS, inspect **Status → Diagnostics → Scripts → Gateway Scripts → Timer** and check execution evidence. A file downloaded from GitHub is not evidence of an installed Gateway Timer.

This project is **fail-closed / not deployment-ready** pending native Gateway validation.
