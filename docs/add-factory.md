# Add a factory

Use a unique lowercase-hyphen factory ID under `factories/`. Register every Gateway and project in `factory.json`, supply native Ignition `project.json` and Perspective resources, declare environment target IDs and a reviewed TEST target registry, and run architecture CI before commissioning any deployment. See [onboarding guide](ADD_FACTORY.md).

Never invent PLC mappings, Gateways or EAM task IDs. A newly created factory remains validation-only until individually commissioned.


Use [the three-factory example](THREE_FACTORY_SHOWCASE.md) to compare a warehouse, a multi-Gateway assembly site and a one-project packaging line.
