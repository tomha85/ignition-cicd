# Deployment guide

`validate.yml` verifies source; `build-release.yml` packages reviewed native resources and an immutable source manifest, **without deployment**. `reusable-deploy.yml` is a guarded TEST Controller staging implementation; `deploy-test.yml` delegates to it when called. The already-registered legacy multi-factory workflow can be used for manual dispatch on the feature branch. Controller staging is not EAM Send Project to Agent. See [qualification gates](RELEASE_QUALIFICATION_GATES.md).
