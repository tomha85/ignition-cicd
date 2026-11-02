#!/usr/bin/env python3
"""Build reproducible native Ignition project ZIP; does NOT deploy or run EAM tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reusable_cicd.core import FrameworkError, load_factory, validate_project

COMMIT=re.compile(r"^[0-9a-f]{40}$")


def build(root: Path, factory_id: str, gateway_id: str, project_name: str,
          sha: str, output: Path) -> dict:
    if not COMMIT.fullmatch(sha):
        raise FrameworkError("40-hex source SHA required")
    factory=load_factory(root/"factories",factory_id)
    gateways=[g for g in factory["gateways"] if g["gateway_id"]==gateway_id]
    if len(gateways)!=1:
        raise FrameworkError("unknown Gateway")
    projects=[x for x in gateways[0]["projects"] if x["name"]==project_name]
    if len(projects)!=1:
        raise FrameworkError("project not assigned to selected Gateway")
    source=projects[0]["source"]
    project_dir=(root/"factories"/factory_id/source)
    validation=validate_project(project_dir,project_name)
    output=output.resolve()
    if output.exists():
        raise FrameworkError("release artifact already exists (no overwrite)")
    if output.is_relative_to(project_dir.resolve()) or output.is_relative_to((root/"factories").resolve()):
        raise FrameworkError("release output cannot be in native source tree")
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest={"factory_id":factory_id,"gateway_id":gateway_id,
              "project":project_name,"git_sha":sha,
              "source_hashes":validation["sha256"],
              "status":"BUILT_NOT_DEPLOYED",
              "eam_agent_task":"NOT_RUN",
              "production_approved":False}
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(validation["sha256"]):
            content=(project_dir/rel).read_bytes()
            info=zipfile.ZipInfo(project_name+"/"+rel,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o644 & 0xFFFF)<<16
            archive.writestr(info,content)
        info=zipfile.ZipInfo("release-manifest.json",date_time=(2020,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    manifest["artifact_sha256"]=hashlib.sha256(output.read_bytes()).hexdigest()
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory",required=True)
    p.add_argument("--gateway",required=True)
    p.add_argument("--project",required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    try:
        print(json.dumps(build(ROOT,args.factory,args.gateway,args.project,args.sha,args.output),indent=2))
    except (FrameworkError,OSError) as exc:
        p.exit(2,"RELEASE_HOLD: "+str(exc)+"\n")


if __name__=="__main__":
    main()
