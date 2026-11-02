# Registered lab targets

lab-targets.json is an EXPLICIT registry of test target identifiers.
Only Factory A FactoryASmoke is authorized for local EAM Controller staging.
All EAM Agent tasks and production promotion are NOT COMMISSIONED.
Any target absent from the approved registry must be rejected by a future
deployer; a factory.json document alone cannot grant device access.
