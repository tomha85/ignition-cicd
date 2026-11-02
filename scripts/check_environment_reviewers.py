#!/usr/bin/env python3
"""Read-only preflight for GitHub's native waiting-for-approval Environment.

If the required reviewer is not configured, output ready=false and exit ZERO.
The next job SKIPS, not FAILS. It can WAIT only once GitHub's required-reviewer
deployment protection rule is configured on the Environment.
"""
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY="tomha85/ignition-cicd"
ENVIRONMENT="ignition-test"
REVIEWER="tomha85"
REF="refs/heads/feat/reusable-multifactory-framework-v1"
REPORT=Path("evidence/ignition-test-review-readiness.json")

def is_required_reviewer_enabled(data):
    if not isinstance(data,dict) or str(data.get("name","")).casefold()!=ENVIRONMENT:
        return False
    for rule in data.get("protection_rules") or []:
        if not isinstance(rule,dict) or rule.get("type")!="required_reviewers":
            continue
        if rule.get("prevent_self_review") is True:
            return False
        for item in rule.get("reviewers") or []:
            if not isinstance(item,dict) or item.get("type") not in ("User",None):
                continue
            reviewer=item.get("reviewer") or item
            if isinstance(reviewer,dict) and str(reviewer.get("login","")).casefold()==REVIEWER:
                return True
    return False

def inspect(token,repository,ref):
    result={"ready":False,"status":"APPROVAL_SETUP_REQUIRED",
            "repository":REPOSITORY,"environment":ENVIRONMENT,
            "required_reviewer":REVIEWER,"controller_stage":"NOT_RUN",
            "agent_send_project":"NOT_RUN","production":"HOLD"}
    if repository!=REPOSITORY or ref!=REF:
        result["reason"]="UNAPPROVED_REPOSITORY_OR_BRANCH"
        return result
    if not token:
        result["reason"]="GITHUB_READ_TOKEN_MISSING"
        return result
    url="https://api.github.com/repos/"+REPOSITORY+"/environments/"+ENVIRONMENT
    req=Request(url,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"ignition-eam-review-readiness"})
    try:
        with urlopen(req,timeout=20) as response:
            if response.status!=200:
                result["reason"]="ENVIRONMENT_API_NOT_SUCCESSFUL"
                return result
            payload=json.load(response)
    except (HTTPError,URLError,OSError,TimeoutError,ValueError):
        result["reason"]="ENVIRONMENT_REVIEW_RULE_NOT_VERIFIED"
        return result
    if not is_required_reviewer_enabled(payload):
        result["reason"]="REQUIRED_REVIEWER_TOMHA85_NOT_ENABLED"
        return result
    result.update({"ready":True,
                   "status":"NATIVE_GITHUB_REVIEWER_GATE_CONFIGURED",
                   "reason":"STAGING_WILL_WAIT_FOR_GITHUB_APPROVAL"})
    return result

def main():
    status=inspect(os.environ.get("GH_REVIEWER_READ_TOKEN",""),
                   os.environ.get("GITHUB_REPOSITORY",""),
                   os.environ.get("GITHUB_REF",""))
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as file:
            file.write("ready="+("true" if status["ready"] else "false")+"\n")
    if status["ready"]:
        print("APPROVAL_RULE_CONFIGURED: stage job will WAIT for GitHub approval")
    else:
        print("APPROVAL_SETUP_REQUIRED_STAGE_SKIPPED: "+status["reason"])
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as file:
            if status["ready"]:
                file.write("### Approval gate ready\n\nThe stage job will WAIT for review by tomha85.\n")
            else:
                file.write("### Controller stage SKIPPED (not deployed)\n\n")
                file.write("To enable WAITING: Settings > Environments > ignition-test > ")
                file.write("Required reviewers > tomha85. Allow self-review if approving your own run.\n\n")
                file.write("Readiness: "+status["reason"]+"\n")
    return 0

if __name__=="__main__":
    sys.exit(main())
