"""Read-only Factory connection metadata qualification (NO Ignition configuration).

The source catalog contains *references* to real Factory connection settings,
not a deployment adapter. Nothing opens database/PLC/OPC UA sockets or
configures an Ignition Gateway. Validation fails closed on unknown Gateway
associations, malformed endpoints, unapproved runtime claims or embedded secrets.
"""
from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from reusable_cicd.core import FrameworkError, discover_factories, load_factory

SCHEMAS = {
    "gateways": ("connection-gateways.schema.json", "gateways"),
    "databases": ("connection-databases.schema.json", "databases"),
    "opcua": ("connection-opcua.schema.json", "opcua_servers"),
    "plc-devices": ("connection-plc-devices.schema.json", "plc_devices"),
}
MAX_FILE_BYTES = 128 * 1024
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
DENIED_KEY_FRAGMENTS = (
    "password", "passwd", "private_key", "api_token", "access_token",
    "connection_string", "client_secret", "shared_secret",
)


def require(ok: bool, why: str) -> None:
    if not ok:
        raise FrameworkError("CONNECTION_METADATA_HOLD: " + why)


def _distinct_object(items):
    """Reject duplicate JSON keys instead of silently accepting last value."""
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _load(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "missing or unsafe JSON")
    require(path.stat().st_size <= MAX_FILE_BYTES, "oversized connection metadata")
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_distinct_object)
    except (UnicodeError, ValueError) as exc:
        raise FrameworkError("CONNECTION_METADATA_HOLD: malformed/duplicate JSON") from exc
    require(isinstance(value, dict), "JSON root must be an object")
    return value


def _spec(value, definition: dict, label: str):
    """Enforce the fixed JSON Schema V1 subset without a runtime pip dependency."""
    expected = definition.get("type")
    if expected == "object":
        require(isinstance(value, dict), label + " must be an object")
        required = definition.get("required", [])
        require(all(key in value for key in required), label + " missing required fields")
        fields = definition.get("properties", {})
        if definition.get("additionalProperties") is False:
            require(set(value).issubset(fields), label + " contains forbidden/unknown fields")
        for key, item in value.items():
            require(not any(fragment in key.lower() for fragment in DENIED_KEY_FRAGMENTS),
                    label + " has prohibited credential material field")
            if key in fields:
                _spec(item, fields[key], label + "." + key)
    elif expected == "array":
        require(isinstance(value, list), label + " must be an array")
        if "minItems" in definition:
            require(len(value) >= definition["minItems"], label + " has too few entries")
        if "maxItems" in definition:
            require(len(value) <= definition["maxItems"], label + " has too many entries")
        for item in value:
            _spec(item, definition["items"], label + ".item")
    elif expected == "integer":
        require(type(value) is int and 1 <= value <= 65535, label + " invalid port")
    elif expected == "string":
        require(isinstance(value, str), label + " must be text")
        require(value == value.strip(), label + " leading or trailing whitespace forbidden")
        require(len(value) >= definition.get("minLength", 0), label + " too short")
        require(len(value) <= definition.get("maxLength", 10_000), label + " too long")
        pattern = definition.get("pattern")
        if pattern:
            require(re.fullmatch(pattern, value) is not None, label + " invalid syntax")
    if "const" in definition:
        require(value == definition["const"] and type(value) is type(definition["const"]),
                label + " must remain " + str(definition["const"]))
    if "enum" in definition:
        require(value in definition["enum"], label + " not in allowed set")


def _host(host: str, label: str) -> None:
    require(isinstance(host, str) and 0 < len(host) <= 253, label + " invalid hostname/IP")
    require(not any(c in host for c in ("/", "@", "\\", " ", "\n", "\r")),
            label + " must contain a hostname/IP, not a URL or credential")
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    require(all(HOST_LABEL.fullmatch(part) for part in host.split(".")),
            label + " invalid hostname")


def _opc_endpoint(endpoint: str) -> None:
    try:
        parsed = urlsplit(endpoint)
        hostname, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise FrameworkError("CONNECTION_METADATA_HOLD: invalid OPC UA endpoint") from exc
    require(parsed.scheme == "opc.tcp" and bool(hostname) and port is not None,
            "OPC UA must specify opc.tcp://host:port")
    require(parsed.username is None and parsed.password is None
            and not parsed.query and not parsed.fragment,
            "OPC UA URL cannot embed credentials/query/fragment")
    require(re.fullmatch(r"[/A-Za-z0-9._~-]*", parsed.path) is not None,
            "unsafe OPC UA URL path")
    _host(hostname, "OPC UA host")


def _check_entry(kind: str, record: dict, gateway_envs: dict[str, set[str]]) -> tuple:
    gateway = record["gateway_id"]
    env = record["environment"]
    require(gateway in gateway_envs, "connection references unregistered Gateway")
    require(env in gateway_envs[gateway],
            "connection environment not declared for selected Gateway")
    require(record["validation_state"] == "DOCUMENTED_NOT_RUNTIME_VERIFIED",
            "static metadata cannot claim a working/field-verified connection")
    require(record["source_reference"].strip() != "",
            "connection requires customer source provenance")
    if kind == "opcua":
        _opc_endpoint(record["endpoint"])
        require(record["security_mode"] == "SignAndEncrypt",
                "insecure OPC UA security mode")
    else:
        _host(record["host"], kind + " host")
    if kind == "gateways":
        return gateway, env
    return gateway, env, record["name"].casefold()


def check_factory_connections(root: Path, factory_id: str,
                              manifest: dict | None = None) -> dict:
    factory_dir = root / "factories" / factory_id
    require(factory_dir.is_dir() and not factory_dir.is_symlink(), "unsafe factory root")
    manifest = manifest if manifest is not None else load_factory(root / "factories", factory_id)
    require(manifest.get("factory_id") == factory_id, "factory identity drift")
    envs = {g["gateway_id"]: set(g["environments"]) for g in manifest["gateways"]}
    base = factory_dir / "connections"
    require(base.is_dir() and not base.is_symlink(), "missing/unsafe connections directory")
    # No silent extra config documents; new categories require a reviewed schema.
    extra = {file.name for file in base.iterdir() if file.suffix == ".json"} - {
        kind + ".json" for kind in SCHEMAS
    }
    require(not extra, "unregistered connection metadata JSON file")
    summary = {"factory_id": factory_id, "metadata_applied_to_gateway": False,
               "runtime_connections_verified": False, "connection_counts": {}}
    for kind, (schema_name, collection) in SCHEMAS.items():
        schema = _load(root / "shared/schemas" / schema_name)
        require(schema.get("$schema") == SCHEMA_DRAFT
                and schema.get("type") == "object"
                and schema.get("additionalProperties") is False,
                "invalid connection schema")
        document = _load(base / (kind + ".json"))
        _spec(document, schema, kind)
        require(document["factory_id"] == factory_id, "connection factory identity drift")
        require(document["deployment_enabled"] is False,
                "connection configuration cannot be automatically deployed")
        rows = document[collection]
        status = document["status"]
        require((status == "NOT_PROVIDED" and len(rows) == 0)
                or (status == "DOCUMENTED_NOT_APPLIED" and len(rows) > 0),
                "connection metadata status/count mismatch")
        seen = set()
        item_spec = schema["properties"][collection]["items"]
        for row in rows:
            # _spec already enforces unknown fields, strict required fields, types,
            # enum values, and explicit references rather than passwords.
            _spec(row, item_spec, kind + " entry")
            key = _check_entry(kind, row, envs)
            require(key not in seen, "duplicate connection assignment")
            seen.add(key)
        summary["connection_counts"][kind] = len(rows)
    return summary


def check_connections(root: Path) -> dict:
    root = root.resolve()
    records = []
    for factory in discover_factories(root / "factories"):
        manifest = load_factory(root / "factories", factory)
        records.append(check_factory_connections(root, factory, manifest))
    return {"status": "CONNECTION_METADATA_VALIDATED_NOT_APPLIED",
            "factory_count": len(records),
            "connection_documents": len(records) * len(SCHEMAS),
            "declared_connections": sum(
                sum(site["connection_counts"].values()) for site in records
            ),
            "connection_catalogs": records,
            "ignition_gateway_configuration": "NOT_RUN",
            "database_runtime": "NOT_TESTED", "opcua_runtime": "NOT_TESTED",
            "plc_communications": "NOT_TESTED",
            "production_approved": False}
