"""Fail closed until the Controller-only native timer exists as an Ignition project resource."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "ignition-project" / "CICDController"
SOURCE = ROOT / "controller" / "eam_trigger_gateway_timer.py"

def validate():
    if not (PROJECT / "project.json").is_file():
        raise RuntimeError("Controller project missing")
    project = json.loads((PROJECT / "project.json").read_text())
    if project.get("title") != "CICDController" or project.get("enabled") is not True:
        raise RuntimeError("Invalid Controller project")
    if not SOURCE.is_file() or "system.eam.runTask" not in SOURCE.read_text():
        raise RuntimeError("EAM trigger source missing")
    # An intentionally strict gate, never infer Ignition resource semantics from an arbitrary .py.
    resources = list(PROJECT.rglob("resource.json"))
    candidates = []
    for item in resources:
        folder = item.parent
        try:
            metadata = json.loads(item.read_text())
        except (ValueError, OSError):
            continue
        pyfiles = list(folder.glob("*.py"))
        if pyfiles and "CICD-AUTO-DeploymentSmokeTest" in "\n".join(p.read_text() for p in pyfiles):
            candidates.append((item,metadata))
    if len(candidates) != 1:
        raise RuntimeError("HOLD: exactly one valid native Controller-only Gateway Timer resource is required; found %s candidate(s)" % len(candidates))
    raise RuntimeError("HOLD: native Ignition 8.3 timer schema and runtime execution not yet independently qualified")

if __name__ == "__main__":
    try:
        validate()
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        sys.exit(2)
