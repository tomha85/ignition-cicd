#!/usr/bin/env python3
"""Verify source checkout provenance before publishing customer release artifacts.

Read-only Git inspection, with no OT access. All customer factory/config source
must be committed to the exact release SHA. Never accepts a caller-provided SHA
as proof without verifying it against the local checkout.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError  # noqa: E402

COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")


def verify_checkout(root: Path, sha: str, *, runner=subprocess.run) -> dict:
    if not isinstance(sha, str) or not COMMIT_SHA.fullmatch(sha):
        raise FrameworkError("CHECKOUT_HOLD: expected exact 40-hex SHA")
    try:
        head = runner(["git", "-C", str(root), "rev-parse", "HEAD"],
                      capture_output=True, text=True, check=True)
        dirty = runner([
            "git", "-C", str(root), "status", "--porcelain=v1",
            "--untracked-files=all", "--", "factories", "config",
            "scripts", "reusable_cicd", "framework", "shared", ".github/workflows",
        ], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FrameworkError("CHECKOUT_HOLD: cannot inspect trusted Git source") from exc
    if head.stdout.strip() != sha:
        raise FrameworkError("CHECKOUT_HOLD: release SHA does not match checkout HEAD")
    if dirty.stdout.strip():
        raise FrameworkError(
            "CHECKOUT_HOLD: factory/config inputs are modified or untracked; commit before release"
        )
    return {
        "source_sha": sha,
        "checkout_commit": "VERIFIED",
        "customer_source_clean": True,
        "deployment": "NOT_RUN",
        "production": "HOLD",
    }


def main():
    parser = argparse.ArgumentParser(description="Strict Git source provenance validation")
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        verify_checkout(ROOT, args.sha)
        print("CUSTOMER_SOURCE_CHECKOUT_VERIFIED_NOT_DEPLOYED")
        return 0
    except FrameworkError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
