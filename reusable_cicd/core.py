"""Read-only, manifest-driven Ignition factory release validation.

This is a V1 qualification harness, not an Ignition deployer. It NEVER contacts
Gateway, EAM, PLC, or OT systems. Existing production/test pipelines are untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_SECRET = re.compile(r"^[A-Z][A-Z0-9_]*$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_ENVIRONMENTS = {"dev", "test", "production"}
_METHODS = {"eam", "direct-test"}


class FrameworkError(ValueError):
    """Invalid source, configuration, policy or release plan."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FrameworkError(message)


def _object(value, label: str) -> dict:
    _require(isinstance(value, dict), label + " must be object")
    return value


def _nonempty(value, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), label + " missing")
    return value


def _load_json(path: Path) -> dict:
    _require(path.is_file() and not path.is_symlink(), "missing/unsafe JSON: " + str(path))
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FrameworkError("invalid JSON: " + str(path)) from exc


def _safe_project_path(factory_dir: Path, source: str) -> Path:
    """Only factory-owned projects; no absolute paths, traversal or symlink escapes."""
    _nonempty(source, "project source")
    _require("\\" not in source and not source.startswith("/"), "unsafe project source")
    parts = PurePosixPath(source).parts
    _require(len(parts) >= 2 and parts[0] == "projects", "project must be under factory projects/")
    _require(all(part not in (".", "..", "") for part in source.split("/")), "project traversal")
    candidate = factory_dir.joinpath(*parts)
    _require(candidate.resolve().is_relative_to((factory_dir / "projects").resolve()),
             "project escapes factory")
    _require(candidate.is_dir(), "project source directory missing: " + source)
    return candidate


def validate_project(project_dir: Path, expected_name: str) -> dict:
    """Validate structurally and hash native resources; no false runtime PASS."""
    _require(project_dir.is_dir(), "project directory missing")
    files = sorted(p for p in project_dir.rglob("*") if p.is_file() or p.is_symlink())
    _require(len(files) >= 2, "project has insufficient native resources")
    for path in [project_dir, *files, *[p for p in project_dir.rglob("*") if p.is_dir()]]:
        _require(not path.is_symlink(), "symlink resource forbidden: " + str(path))
    meta = _load_json(project_dir / "project.json")
    _require(meta.get("title") == expected_name, "Ignition project title mismatch: " + expected_name)
    descriptors = list(project_dir.rglob("resource.json"))
    _require(descriptors, "native Ignition resource.json missing")
    for descriptor in descriptors:
        resource = _load_json(descriptor)
        declared = resource.get("files")
        _require(isinstance(declared, list) and bool(declared), "invalid resource file list")
        for item in declared:
            _require(isinstance(item, str) and item not in ("", ".", "..")
                     and "/" not in item and "\\" not in item,
                     "unsafe resource filename")
            _require((descriptor.parent / item).is_file(), "resource dependency missing: " + item)
    for file in files:
        rel = file.relative_to(project_dir).as_posix()
        name = file.name.lower()
        _require(not any(s in name for s in
                         (".env", ".pem", ".key", "password", "secret", "credential", ".gwbk")),
                 "secret-like file not allowed in project: " + rel)
        if file.suffix.lower() == ".json":
            _load_json(file)
    hashes = {file.relative_to(project_dir).as_posix():
              hashlib.sha256(file.read_bytes()).hexdigest() for file in files}
    return {"name": expected_name, "file_count": len(files), "sha256": hashes,
            "native_structure": "VALIDATED_NOT_RUNTIME_TESTED"}


def load_factory(catalog: Path, factory_id: str) -> dict:
    _require(bool(_ID.fullmatch(factory_id)), "invalid factory identifier")
    catalog = catalog.resolve()
    directory = catalog / factory_id
    _require(directory.is_dir() and not directory.is_symlink(),
             "factory directory missing/unsafe: " + factory_id)
    data = _load_json(directory / "factory.json")
    _require(data.get("schema_version") == 1, "unsupported factory schema")
    _require(data.get("factory_id") == factory_id, "factory id / directory mismatch")
    _require(data.get("ignition_version") == "8.3", "only Ignition 8.3 validated in V1")
    gateways = data.get("gateways")
    _require(isinstance(gateways, list) and gateways, "factory needs at least one Gateway")
    seen_gateways = set()
    seen_envs = set()
    for gateway in gateways:
        gateway = _object(gateway, "Gateway")
        gateway_id = gateway.get("gateway_id")
        _require(isinstance(gateway_id, str) and _ID.fullmatch(gateway_id),
                 "invalid gateway_id")
        _require(gateway_id not in seen_gateways, "duplicate Gateway: " + gateway_id)
        seen_gateways.add(gateway_id)
        projects = gateway.get("projects")
        _require(isinstance(projects, list) and projects, "Gateway needs projects")
        names = set()
        for project in projects:
            project = _object(project, "project")
            name = project.get("name")
            _require(isinstance(name, str) and _PROJECT.fullmatch(name),
                     "invalid Ignition project name")
            _require(name not in names, "duplicate project on Gateway: " + name)
            names.add(name)
            source = project.get("source")
            path = _safe_project_path(directory, source)
            validate_project(path, name)
        environments = _object(gateway.get("environments"), "environments")
        _require(bool(environments), "Gateway needs an environment")
        _require(set(environments).issubset(_ENVIRONMENTS), "unknown environment type")
        for env, settings in environments.items():
            settings = _object(settings, env)
            github_env = _nonempty(settings.get("github_environment"), "github_environment")
            _require(bool(_ID.fullmatch(github_env)), "invalid GitHub environment identifier")
            _require(github_env not in seen_envs, "duplicate GitHub environment in factory")
            seen_envs.add(github_env)
            method = settings.get("deployment_method")
            _require(method in _METHODS, "unsupported deployment method")
            _nonempty(settings.get("target_id"), "target_id")
            if method == "direct-test":
                _require(env != "production", "direct-test cannot target production")
            secret_refs = settings.get("secret_refs", [])
            _require(isinstance(secret_refs, list), "secret_refs must be a list")
            _require(len(secret_refs) == len(set(str(x) for x in secret_refs)),
                     "duplicate secret reference")
            _require(all(isinstance(s, str) and bool(_SECRET.fullmatch(s))
                         for s in secret_refs), "secret_refs contain invalid identifier/value")
            # This version has NO deploy command; a future deploy adapter must
            # independently enforce approval and qualified environment policy.
            _require(settings.get("deployment_enabled") is False,
                     "V1 requires deployment_enabled=false")
            if env == "production":
                _require(settings.get("approval_required") is True,
                         "production requires engineer approval")
    return data


def discover_factories(catalog: Path) -> list[str]:
    _require(catalog.is_dir(), "factory catalog missing: " + str(catalog))
    return sorted(p.name for p in catalog.iterdir()
                  if p.is_dir() and (p / "factory.json").is_file())


def validate_catalog(catalog: Path) -> list[str]:
    factories = discover_factories(catalog)
    _require(bool(factories), "empty factory catalog")
    environment_names = {}
    target_scope = {}
    for factory in factories:
        data = load_factory(catalog, factory)
        for gateway in data["gateways"]:
            for env, settings in gateway["environments"].items():
                name = settings["github_environment"]
                _require(name not in environment_names, "cross-factory GitHub environment collision: " + name)
                environment_names[name] = factory
                target = (env, settings["target_id"])
                _require(target not in target_scope,
                         "cross-factory target collision: " + str(target))
                target_scope[target] = factory
    return factories


def plan_release(catalog: Path, factory_id: str, gateway_id: str,
                 environment: str, source_sha: str) -> dict:
    _require(bool(_COMMIT.fullmatch(source_sha)), "full Git SHA required")
    _require(environment in _ENVIRONMENTS, "unknown environment")
    data = load_factory(catalog, factory_id)
    gateway = next((g for g in data["gateways"] if g["gateway_id"] == gateway_id), None)
    _require(gateway is not None, "unknown Gateway")
    env = gateway["environments"].get(environment)
    _require(env is not None, "environment not configured")
    root = catalog.resolve() / factory_id
    projects = [validate_project(_safe_project_path(root, p["source"]), p["name"])
                for p in gateway["projects"]]
    return {
        "schema_version": 1,
        "factory_id": factory_id,
        "gateway_id": gateway_id,
        "environment": environment,
        "github_environment": env["github_environment"],
        "target_id": env["target_id"],
        "deployment_method": env["deployment_method"],
        "source_sha": source_sha,
        "projects": projects,
        "secret_refs": env.get("secret_refs", []),
        "status": "VALIDATED_NOT_DEPLOYED",
        "test_gateway": "NOT_TESTED",
        "browser_render": "NOT_TESTED",
        "fat": "NOT_TESTED",
        "production_approved": False,
        "deployment_authorized": False,
    }
