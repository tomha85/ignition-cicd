#!/usr/bin/env python3
"""Optional read-only private EAM Controller TLS preflight.

This performs a socket+TLS handshake ONLY, with the configured Controller's
trusted certificate authority. It does not send HTTP, authenticate, execute
an EAM task, access PLCs, write project files, or claim EAM readiness.
Run manually on a trusted network-connected runner. Never on untrusted PRs.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError  # noqa: E402
from scripts.customer_plan import load_profile  # noqa: E402


def require(condition, reason):
    if not condition:
        raise FrameworkError("NETWORK_PREFLIGHT_HOLD: " + reason)


def probe(profile, controller_id, ca_file, *, socket_opener=None,
          tls_context_factory=None):
    require(profile.get("schema_version") == 2, "v2 customer topology required")
    matches = [x for x in profile["controllers"]
               if x["controller_id"] == controller_id]
    require(len(matches) == 1, "unknown/duplicate controller_id")
    controller = matches[0]
    require(isinstance(ca_file, Path) and ca_file.is_file() and
            not ca_file.is_symlink(), "real trusted CA file required")
    url = urlsplit(controller["controller_url"])
    require(url.scheme == "https" and url.hostname and url.port,
            "invalid Controller HTTPS endpoint")
    opener = socket_opener or socket.create_connection
    context_factory = tls_context_factory or ssl.create_default_context
    context = context_factory(cafile=str(ca_file))
    # Actual DNS, network ACLs and CA validation happen at handshake.
    # The host must be reachable from the trusted runner, not necessarily
    # from the GitHub-hosted public CI network.
    with opener((url.hostname, url.port), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=url.hostname):
            pass
    return {
        "controller_id": controller_id,
        "hosting": controller["hosting"],
        "network": controller["network"],
        "status": "TLS_HANDSHAKE_VERIFIED",
        "eam_agent_registered": "NOT_TESTED",
        "eam_api_authorized": "NOT_TESTED",
        "controller_project_stage": "NOT_RUN",
        "eam_send_project": "NOT_RUN",
        "production": "HOLD",
    }


def main():
    p = argparse.ArgumentParser(description="Read-only HTTPS/TLS EAM reachability")
    p.add_argument("--config", required=True)
    p.add_argument("--controller", required=True)
    p.add_argument("--ca-file", required=True)
    p.add_argument("--confirm", required=True,
                   help="must be READ_ONLY_TLS_PREFLIGHT")
    p.add_argument("--output", default=None)
    args = p.parse_args()
    try:
        require(args.confirm == "READ_ONLY_TLS_PREFLIGHT",
                "explicit operator confirmation required")
        profile = load_profile(Path(args.config))
        report = probe(profile, args.controller, Path(args.ca_file))
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(serialized, encoding="utf-8")
        print(serialized)
        return 0
    except (FrameworkError, OSError, ssl.SSLError, socket.timeout,
            ConnectionError, ValueError) as exc:
        # Do not leak customer endpoint or certificate details into CI logs.
        print("NETWORK_PREFLIGHT_HOLD: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
