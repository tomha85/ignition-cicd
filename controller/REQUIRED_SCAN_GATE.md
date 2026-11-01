# REQUIRED: Controller project scan / runtime verification

**NOT IMPLEMENTED**: The sample deployer stages file-based project resources on the Controller, but does not establish that the running Gateway loaded that precise version before invoking EAM.

Before treating this as valid E2E deployment, implement an authenticated project scan using Ignition 8.3's documented /data/api/v1/scan/projects interface or another supported mechanism, then verify the loaded project/resource version before trigger.

Current pipeline status is LAB STARTER / NOT QUALIFIED. Never use in production.
