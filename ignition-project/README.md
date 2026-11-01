# Real Ignition project required

Copy the actual Ignition **8.3 file-based** project directory from Designer/Gateway into:

`ignition-project/DeploymentSmokeTest/`

It must contain real `project.json` and project resources. Do not fabricate an empty project or simply unzip an unrelated project export. CI intentionally FAILS until this exists. Static Perspective label is sufficient for first smoke test.
