#!/usr/bin/env python3
"""Validate multi-factory repository structure, source parity and safety gates."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reusable_cicd.core import FrameworkError
from framework.validation.structure import qualify_repository

if __name__ == "__main__":
    try:
        print(json.dumps(qualify_repository(ROOT), indent=2))
    except (FrameworkError, ValueError, OSError) as exc:
        raise SystemExit("ARCHITECTURE_HOLD: " + str(exc)) from exc
