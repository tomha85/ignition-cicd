"""Multi-factory TEST-only EAM release planning and fail-closed deployment gate.

This script intentionally does not impersonate a functioning Controller bridge.
EAM execution needs a commissioned, authenticated native Ignition Controller bridge
that proves task completion and independently verifies each Agent.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "manifests/eam-multi-factory-lab.json"
PROJECT_BASE = ROOT / "ignition-project"
REQUIRED = {
    "factory_a": ("WarehouseHMI", "EAM-Factory-A", "CICD-SEND-WarehouseHMI-A"),
    "factory_b": ("ConveyorHMI", "EAM-Factory-B", "CICD-SEND-ConveyorHMI-B"),
    "factory_c": ("PackagingHMI", "EAM-Factory-C", "CICD-SEND-PackagingHMI-C"),
}

def validate_registry():
    config = json.loads(REGISTRY.read_text())
    if config.get("environment") != "ignition-test" or config.get("production_approved") is not False:
        raise RuntimeError("HOLD: production or unauthorized EAM registry")
    targets = config.get("targets", {})
    if set(targets) != set(REQUIRED):
        raise RuntimeError("HOLD: unexpected factory list")
    for factory, (project, agent, task) in REQUIRED.items():
        entry = targets[factory]
        if (entry.get("project"), entry.get("agent"), entry.get("task")) != (project, agent, task):
            raise RuntimeError("HOLD: unapproved factory to project/agent/task mapping: " + factory)
        if entry.get("source_path") != "ignition-project/" + project:
            raise RuntimeError("HOLD: unexpected project source path")
        base = PROJECT_BASE / project
        paths = (
            "project.json",
            "com.inductiveautomation.perspective/page-config/config.json",
            "com.inductiveautomation.perspective/views/Main/view.json",
        )
        if not all((base / item).is_file() for item in paths):
            raise RuntimeError("HOLD: missing native Ignition project resource: " + project)
        if any(p.is_symlink() for p in base.rglob("*")):
            raise RuntimeError("HOLD: symlinked project resources")
        data = json.loads((base / paths[-1]).read_text())
        labels = [x.get("props", {}).get("text") for x in data["root"]["children"]]
        if not any(factory.replace("_", " ").upper() in str(x).upper() for x in labels):
            raise RuntimeError("HOLD: project factory identifier mismatch")
        for file in base.rglob("*.json"):
            json.loads(file.read_text())
    return config

def release_plan(factory, sha):
    config = validate_registry()
    if factory not in REQUIRED:
        raise RuntimeError("HOLD: unknown factory")
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError("HOLD: invalid commit SHA")
    entry = config["targets"][factory]
    base = ROOT / entry["source_path"]
    checksums = {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in base.rglob("*") if p.is_file()}
    return {"mode":"EAM_MULTI_FACTORY_TEST", "factory":factory,
            "project":entry["project"],"target_agent":entry["agent"],
            "eam_task":entry["task"],"release_sha":sha,
            "file_hashes":checksums, "staging":"NOT_RUN",
            "eam_task_status":"NOT_RUN", "agent_verification":"NOT_RUN",
            "deployment":"HOLD"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--factory", choices=sorted(REQUIRED))
    parser.add_argument("--sha")
    parser.add_argument("--deploy", action="store_true")
    args=parser.parse_args()
    if args.validate:
        validate_registry()
        print("MULTI_FACTORY_3_PROJECTS_VALIDATED")
        return
    if not args.factory or not args.sha:
        parser.error("--factory and --sha are required")
    plan=release_plan(args.factory, args.sha)
    output=ROOT / "evidence/eam-multi-factory.json"
    output.parent.mkdir(exist_ok=True)
    if args.deploy:
        plan["reason"] = ("HOLD: native Controller EAM automation bridge and task receipts "
                          "are not installed/qualified for this factory. No Gateway changed.")
    output.write_text(json.dumps(plan,indent=2)+"\n")
    print(json.dumps(plan,indent=2))
    if args.deploy:
        raise RuntimeError(plan["reason"])

if __name__=="__main__":
    main()
