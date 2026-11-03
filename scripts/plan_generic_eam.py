#!/usr/bin/env python3
"""Generate a read-only, validated EAM plan. Never deploys or contacts OT."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from framework.deployment.generic_eam import resolve

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--gateway")
    p.add_argument("--environment", default="test")
    args = p.parse_args()
    try:
        print(json.dumps(resolve(ROOT, args.factory, args.project,
                                 args.environment, args.gateway),
                         indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print("GENERIC_EAM_HOLD: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
