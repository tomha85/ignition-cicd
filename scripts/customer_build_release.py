#!/usr/bin/env python3
"""Build native Ignition release artifacts from any validated customer profile.

Offline only. Reuses the established V3 native source ZIP builder. It never
connects to Ignition/EAM/PLC or grants production deployment permission.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reusable_cicd.core import FrameworkError  # noqa: E402
from scripts.customer_plan import build_plan, load_profile  # noqa: E402
from scripts.build_release_v3 import build  # noqa: E402


def make_releases(root: Path, profile: dict, sha: str, outdir: Path, *,
                  factory=None, gateway=None, project=None):
    """One immutable artifact per exact configured Factory/Gateway/Project."""
    plan = build_plan(root, profile, sha, factory=factory,
                      gateway=gateway, project=project)
    if plan["status"] != "VALIDATED_NOT_DEPLOYED":
        raise FrameworkError("CUSTOMER_RELEASE_HOLD: source plan not validated")
    # Match the validated v2 topology contract (up to 500 explicit targets).
    # Never truncate a customer configuration silently. Large CI builds must
    # have sufficient runner time/storage or be split via exact target filters.
    if len(plan["targets"]) > 500:
        raise FrameworkError("CUSTOMER_RELEASE_HOLD: maximum 500 targets per release")
    destination = outdir.resolve()
    if destination.is_relative_to((root / "factories").resolve()):
        raise FrameworkError("CUSTOMER_RELEASE_HOLD: artifacts cannot be inside native sources")
    if destination.is_relative_to((root / "config").resolve()):
        raise FrameworkError("CUSTOMER_RELEASE_HOLD: artifacts cannot be inside config")
    artifacts = []
    for selection in plan["targets"]:
        fac = selection["factory_id"]
        gw = selection["gateway_id"]
        proj = selection["project"]
        # IDs come from validated manifests; never permit supplied file paths.
        archive = destination / fac / gw / (proj + "-" + sha[:12] + ".zip")
        result = build(root, fac, gw, proj, sha, archive)
        item = {
            "factory_id": fac,
            "gateway_id": gw,
            "project": proj,
            "archive": archive.relative_to(destination).as_posix(),
            "archive_sha256": result["artifact_sha256"],
            "native_source_hashes": selection["source_sha256"],
            "status": "BUILT_NOT_DEPLOYED",
            "eam_send_project": "NOT_RUN",
            "production_approved": False,
        }
        if "site_id" in selection:
            item["site_id"] = selection["site_id"]
            item["workshop_id"] = selection["workshop_id"]
            item["controller_id"] = selection["controller_id"]
        artifacts.append(item)
    return {
        "schema_version": profile["schema_version"],
        "customer_id": profile["customer_id"],
        "source_sha": sha,
        "status": "CUSTOMER_NATIVE_RELEASES_BUILT_NOT_DEPLOYED",
        "release_count": len(artifacts),
        "releases": artifacts,
        "eam_task": "NOT_RUN",
        "runtime_fat": "NOT_TESTED",
        "production": "HOLD",
    }


def main():
    parser = argparse.ArgumentParser(description="Build customer native Ignition ZIPs (NO DEPLOY)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--factory", default=None)
    parser.add_argument("--gateway", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args()
    try:
        profile = load_profile(Path(args.config))
        report = make_releases(ROOT, profile, args.sha, Path(args.output_dir),
                               factory=args.factory, gateway=args.gateway,
                               project=args.project)
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.evidence:
            path = Path(args.evidence)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
        print(output)
        return 0
    except (FrameworkError, OSError, ValueError) as exc:
        print("CUSTOMER_RELEASE_HOLD: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
