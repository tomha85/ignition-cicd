#!/usr/bin/env python3
"""Generic read-only factory manifest validator / release-plan CLI."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reusable_cicd.core import FrameworkError, load_factory, plan_release, validate_catalog

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ignition 8.3 multi-factory validation (NO DEPLOY)")
    parser.add_argument("--catalog", type=Path, default=ROOT / "factories")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-catalog", action="store_true")
    group.add_argument("--factory")
    parser.add_argument("--gateway")
    parser.add_argument("--environment", choices=["dev", "test", "production"])
    parser.add_argument("--sha", help="full 40-character Git commit")
    args = parser.parse_args()
    try:
        if args.check_catalog:
            if args.gateway or args.environment or args.sha:
                parser.error("--check-catalog cannot take --gateway/--environment/--sha")
            print(json.dumps({"catalog": validate_catalog(args.catalog),
                              "status": "VALIDATED_NOT_DEPLOYED"}, indent=2))
        elif args.gateway and args.environment and args.sha:
            validate_catalog(args.catalog)
            print(json.dumps(plan_release(args.catalog, args.factory, args.gateway,
                                          args.environment, args.sha), indent=2))
        elif not args.gateway and not args.environment and not args.sha:
            print(json.dumps({"factory_id": args.factory,
                              "status": "VALIDATED_NOT_DEPLOYED",
                              "manifest": load_factory(args.catalog, args.factory)}, indent=2))
        else:
            parser.error("release plan requires all of --gateway --environment --sha")
    except FrameworkError as exc:
        parser.exit(2, "HOLD: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
