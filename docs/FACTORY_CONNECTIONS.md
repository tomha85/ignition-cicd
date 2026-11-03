# Factory Connections: Gateway IP, Database, OPC UA, PLC inventory

These are **configuration metadata files only**. Nothing in this feature creates live Ignition connections or talks to an OT network.

## Where to edit each factory

| File within factories/<factory-id>/connections/ | Purpose |
|---|---|
| gateways.json | Gateway hostname/IP, environment and HTTPS management port |
| databases.json | Database host/IP, port, driver, database name and secret reference |
| opcua.json | External OPC UA endpoint, secure mode/policy and certificate reference |
| plc-devices.json | PLC host/IP, vendor, protocol and port |

The current factory IDs are lab-warehouse, lab-assembly and lab-packaging. Each has the four files. Their contents are initially NOT_PROVIDED and empty because authentic IPs, DB names, OPC endpoints and PLC mappings have not been provided or verified.

Do not confuse these connection catalogs with factory.json (which maps Factory → Gateway → Project), gateways/<gateway-id>/config/gateway.json (curated Gateway export metadata), environments/<env>.json (target IDs), or targets/lab-targets.json (reviewed isolated TEST staging authorization).

## Examples for a hypothetical TEST site — NOT LIVE endpoints

All hostnames ending in .example.invalid are intentionally nonfunctional. Replace only with independently supplied and reviewed factory documentation. Never commit fabricated PLC or OPC associations.

### gateways.json

```json
{
  "schema_version": 1,
  "factory_id": "lab-warehouse",
  "status": "DOCUMENTED_NOT_APPLIED",
  "deployment_enabled": false,
  "gateways": [
    {
      "gateway_id": "warehouse-main",
      "environment": "test",
      "host": "gateway.example.invalid",
      "https_port": 8043,
      "source_reference": "CUSTOMER_GATEWAY_EXPORT_2026",
      "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED"
    }
  ]
}
```

### databases.json

```json
{
  "schema_version": 1,
  "factory_id": "lab-warehouse",
  "status": "DOCUMENTED_NOT_APPLIED",
  "deployment_enabled": false,
  "databases": [
    {
      "name": "PlantHistorian",
      "gateway_id": "warehouse-main",
      "environment": "test",
      "driver": "postgresql",
      "host": "db-historian.example.invalid",
      "port": 5432,
      "database": "historian",
      "credential_ref": "WAREHOUSE_HISTORIAN_DB",
      "source_reference": "CUSTOMER_DATABASE_CONFIG_2026",
      "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED"
    }
  ]
}
```

### opcua.json

```json
{
  "schema_version": 1,
  "factory_id": "lab-warehouse",
  "status": "DOCUMENTED_NOT_APPLIED",
  "deployment_enabled": false,
  "opcua_servers": [
    {
      "name": "ProductionOPC",
      "gateway_id": "warehouse-main",
      "environment": "test",
      "endpoint": "opc.tcp://opc.example.invalid:4840/UA/Server",
      "security_policy": "Basic256Sha256",
      "security_mode": "SignAndEncrypt",
      "certificate_ref": "WAREHOUSE_OPC_CERT",
      "source_reference": "CUSTOMER_OPC_EXPORT_2026",
      "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED"
    }
  ]
}
```

### plc-devices.json

```json
{
  "schema_version": 1,
  "factory_id": "lab-warehouse",
  "status": "DOCUMENTED_NOT_APPLIED",
  "deployment_enabled": false,
  "plc_devices": [
    {
      "name": "PLC_001",
      "gateway_id": "warehouse-main",
      "environment": "test",
      "vendor": "Rockwell",
      "protocol": "ethernet-ip",
      "host": "plc-001.example.invalid",
      "port": 44818,
      "source_reference": "CUSTOMER_PLC_INVENTORY_2026",
      "validation_state": "DOCUMENTED_NOT_RUNTIME_VERIFIED"
    }
  ]
}
```

## Required rules

1. Backup your branch before any edit. Only modify the chosen factory's connection files; do not change source project files just to supply IPs.
2. Keep schema_version=1, factory_id identical to the folder, and deployment_enabled=false.
3. Empty catalog: status=NOT_PROVIDED and [] entries. With documented entries: status=DOCUMENTED_NOT_APPLIED.
4. Every record has a source_reference and validation_state=DOCUMENTED_NOT_RUNTIME_VERIFIED. A documented endpoint is not a proven online connection.
5. gateway_id must exist in that factory's factory.json, and environment must actually be configured for that Gateway. Duplicate assignments and unsafe endpoint syntax fail validation.
6. Never store a database password, API token, OPC UA key, connection string or real credential in these files. The credential_ref / certificate_ref fields contain alias names only. Actual credentials belong in a vault or protected Environment.
7. Use a PRIVATE repository or a protected configuration store for real site network inventory. Publishing sensitive OT IP/hostname data in a public GitHub repository is unsafe.
8. Gateways, database sources, OPC UA servers and PLCs are not deployed automatically. In Ignition they require separate runtime Gateway configuration, credentials/cert trust, connection testing and engineering approval.

## Validate locally or in GitHub CI

```bash
python framework/cli/check_repo.py
python -m unittest discover -s tests -v
```

Schema contracts are under shared/schemas/connection-*.schema.json, and the strict Python validator is framework/validation/connections.py. The normal two-job workflow still runs Validate → GitHub Required Reviewer approval → Stage TEST Controller. Only native project source staging is performed; connection declarations are read-only.

## Status boundaries

- Metadata validation is not database login, PLC communications, OPC session, device discovery, network reachability or mapping validation.
- A live installation needs independent vendor-supported configuration adapters, backups, target commissioning, approvals and FAT evidence.
- EAM Send Project tasks and production remain explicitly unauthorized.
