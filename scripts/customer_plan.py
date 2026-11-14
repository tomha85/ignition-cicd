#!/usr/bin/env python3
"""Read-only customer CI/CD plan: manifest-driven, fork-safe, no Gateway writes.

The profile is a set of customer-supplied EAM connection *references*, not a
runtime authorization. This tool NEVER contacts Ignition, EAM, PLCs, or GitHub.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reusable_cicd.core import (  # noqa: E402
    FrameworkError, load_factory, plan_release, validate_catalog,
)

CUSTOMER_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
REF = re.compile(r"[A-Z][A-Z0-9_]*\Z")
AGENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
PROFILE_KEYS = {"schema_version", "customer_id", "mode", "targets"}
TARGET_KEYS = {"factory_id", "gateway_id", "project", "eam"}
EAM_KEYS = {
    "controller_url", "agent_name", "network", "api_token_secret",
    "ca_file_variable",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise FrameworkError("CUSTOMER_CONFIG_HOLD: " + reason)


def reject_duplicate_keys(pairs):
    data = {}
    for key, value in pairs:
        require(key not in data, "duplicate JSON key")
        data[key] = value
    return data


def load_profile(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "configuration file unavailable/unsafe")
    require(path.stat().st_size <= 128 * 1024, "configuration file too large")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"),
                             object_pairs_hook=reject_duplicate_keys)
    except (UnicodeError, ValueError) as exc:
        raise FrameworkError("CUSTOMER_CONFIG_HOLD: invalid JSON") from exc
    require(isinstance(profile, dict) and set(profile) == PROFILE_KEYS,
            "invalid profile fields")
    require(type(profile["schema_version"]) is int and profile["schema_version"] == 1,
            "unsupported profile version")
    require(isinstance(profile["customer_id"], str) and
            bool(CUSTOMER_ID.fullmatch(profile["customer_id"])),
            "invalid customer identifier")
    require(profile["mode"] == "plan_only",
            "only plan_only is supported; this is NOT a deployment authorization")
    targets = profile["targets"]
    require(isinstance(targets, list) and 0 < len(targets) <= 200,
            "provide 1 to 200 explicit factory/Gateway/project targets")
    seen = set()
    for target in targets:
        require(isinstance(target, dict) and set(target) == TARGET_KEYS,
                "invalid target fields")
        for name in ("factory_id", "gateway_id", "project"):
            require(isinstance(target[name], str) and bool(target[name]),
                    "missing " + name)
        key = (target["factory_id"], target["gateway_id"], target["project"])
        require(key not in seen, "duplicate factory/Gateway/project target")
        seen.add(key)
        eam = target["eam"]
        require(isinstance(eam, dict) and set(eam) == EAM_KEYS,
                "invalid EAM connection reference fields")
        for field in ("api_token_secret", "ca_file_variable"):
            value = eam[field]
            require(isinstance(value, str) and bool(REF.fullmatch(value)),
                    "invalid " + field + " (use GitHub secret/variable NAME only)")
        require(isinstance(eam["agent_name"], str) and
                bool(AGENT.fullmatch(eam["agent_name"])),
                "invalid EAM Agent name")
        require(eam["network"] in ("private_vpn", "private_wan"),
                "EAM connectivity must be via a reviewed private network")
        endpoint = eam["controller_url"]
        require(isinstance(endpoint, str), "missing Controller HTTPS URL")
        try:
            parsed = urlsplit(endpoint)
            valid_port = parsed.port
        except ValueError as exc:
            raise FrameworkError("CUSTOMER_CONFIG_HOLD: invalid Controller URL") from exc
        require(parsed.scheme == "https" and parsed.hostname and
                valid_port is not None and 1 <= valid_port <= 65535 and
                not parsed.username and not parsed.password and
                not parsed.path.strip("/") and not parsed.query and
                not parsed.fragment and not any(c.isspace() for c in endpoint),
                "Controller must be a HTTPS base URL with explicit port and no credentials")
    return profile


def build_plan(root: Path, profile: dict, sha: str, *, factory=None,
               gateway=None, project=None) -> dict:
    validate_catalog(root / "factories")
    selected = []
    for target in profile["targets"]:
        if ((factory is not None and factory != target["factory_id"]) or
                (gateway is not None and gateway != target["gateway_id"]) or
                (project is not None and project != target["project"])):
            continue
        fac = target["factory_id"]
        gw = target["gateway_id"]
        proj = target["project"]
        release = plan_release(root / "factories", fac, gw, "test", sha)
        matches = [p for p in release["projects"] if p["name"] == proj]
        require(len(matches) == 1, "project is not registered on selected Gateway")
        gateway_manifest = next(
            g for g in load_factory(root / "factories", fac)["gateways"]
            if g["gateway_id"] == gw)
        source = next(p["source"] for p in gateway_manifest["projects"]
                      if p["name"] == proj)
        selected.append({
            "factory_id": fac,
            "gateway_id": gw,
            "project": proj,
            "native_source": "factories/" + fac + "/" + source,
            "source_files": matches[0]["file_count"],
            "source_sha256": matches[0]["sha256"],
            "eam_agent_name": target["eam"]["agent_name"],
            "transport": target["eam"]["network"],
            "controller_url": "CONFIGURED_NOT_CONNECTED",
            "credentials": "REFERENCED_NOT_READ",
            "stage": "NOT_RUN",
            "eam_send_project": "NOT_RUN",
            "gateway_runtime": "NOT_TESTED",
            "browser_fat": "NOT_TESTED",
            "deployment_authorized": False,
        })
    require(bool(selected), "no configured target matched the selection")
    return {
        "schema_version": 1,
        "customer_id": profile["customer_id"],
        "source_sha": sha,
        "mode": "plan_only",
        "status": "VALIDATED_NOT_DEPLOYED",
        "factory_count": len({t["factory_id"] for t in selected}),
        "target_count": len(selected),
        "targets": selected,
        "external_network": "NOT_TESTED",
        "eam_task": "NOT_EXECUTED",
        "production": "HOLD",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a customer-specific Ignition CI/CD plan without deployment")
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha", required=True, help="40-character Git release SHA")
    parser.add_argument("--factory", default=None)
    parser.add_argument("--gateway", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--output", default=None, help="write JSON test evidence")
    args = parser.parse_args()
    try:
        profile = load_profile(Path(args.config))
        result = build_plan(ROOT, profile, args.sha, factory=args.factory,
                            gateway=args.gateway, project=args.project)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
        print(rendered)
        return 0
    except (FrameworkError, ValueError, OSError) as exc:
        print("CUSTOMER_PLAN_HOLD: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
