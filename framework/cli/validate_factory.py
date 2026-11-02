#!/usr/bin/env python3
"""Read-only factory/project release plan. No network, Docker or Gateway writes."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from framework.validation.manifest import selected_test_plan
from reusable_cicd.core import FrameworkError


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory",required=True)
    p.add_argument("--gateway",required=True)
    p.add_argument("--project",required=True)
    p.add_argument("--sha",required=True)
    args=p.parse_args()
    try:
        result=selected_test_plan(ROOT,args.factory,args.gateway,args.sha)
        projects=[x for x in result["projects"] if x["name"]==args.project]
        if len(projects)!=1:
            raise FrameworkError("project not registered on selected Gateway")
        print(json.dumps({"factory_id":args.factory,"gateway_id":args.gateway,
                          "project":args.project,"sha":args.sha,
                          "source_hashes":projects[0]["sha256"],
                          "status":"VALIDATED_NOT_DEPLOYED",
                          "agent_send_project":"NOT_RUN",
                          "production_approved":False},indent=2))
    except FrameworkError as exc:
        p.exit(2,"HOLD: "+str(exc)+"\n")


if __name__=="__main__":
    main()
