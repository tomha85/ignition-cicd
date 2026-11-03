#!/usr/bin/env python3
"""Fail-closed GitHub required-reviewer evidence gate for isolated EAM TEST staging.

Environment approval is configured in GitHub Settings, NOT inside a workflow.
This check independently verifies that the actual user tomha85 approved the
current run's ignition-test deployment before any TEST Controller mutation.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/factory-a-approval.json"
REPOSITORY = "tomha85/ignition-cicd"
STAGING_REFS = frozenset(("refs/heads/main", "refs/heads/feat/reusable-multifactory-framework-v1", "refs/heads/feat/generic-multifactory-eam-engine-v1-20261103"))
ENVIRONMENT = "ignition-test"
REVIEWER = "tomha85"
ALLOWED_EVENTS = ("push", "workflow_dispatch")


class ApprovalHold(RuntimeError):
    """Deployment is not authorized. Nothing on the Controller may be changed."""


def require(condition, reason):
    if not condition:
        raise ApprovalHold("HOLD: " + reason)


def validate_context(context):
    require(context.get("GITHUB_REPOSITORY") == REPOSITORY, "wrong GitHub repository")
    require(context.get("GITHUB_REF") in STAGING_REFS, "staging restricted to main or reviewed feature branch")
    require(context.get("GITHUB_EVENT_NAME") in ALLOWED_EVENTS, "unexpected event")
    require(re.fullmatch(r"[0-9a-f]{40}", context.get("GITHUB_SHA", "")), "invalid release SHA")
    number = context.get("GITHUB_RUN_ID", "")
    require(bool(re.fullmatch(r"[1-9][0-9]{0,15}", number)), "missing or invalid run ID")
    # GitHub's review history is at RUN scope, not per re-run attempt.
    # Require a new run instead of reusing approval from an older attempt.
    require(context.get("GITHUB_RUN_ATTEMPT") == "1",
            "re-run attempts require a fresh workflow run and fresh approval")
    return number


def approved_review(reviews):
    """Return evidence for the exact run, approved user and target environment."""
    require(isinstance(reviews, list), "invalid GitHub approval history")
    for review in reviews:
        if not isinstance(review, dict):
            continue
        user = review.get("user") or {}
        environments = review.get("environments") or []
        if (str(review.get("state", "")).lower() == "approved"
                and isinstance(user, dict)
                and user.get("login", "").lower() == REVIEWER
                and isinstance(environments, list)
                and any(isinstance(env, dict) and
                        env.get("name", "").lower() == ENVIRONMENT
                        for env in environments)):
            return {"reviewer": REVIEWER, "environment": ENVIRONMENT,
                    "review_state": "approved"}
    raise ApprovalHold("HOLD: current run has NO approval by "
                       + REVIEWER + " for " + ENVIRONMENT)


def fetch_approvals(token, run_id):
    require(bool(token), "GitHub Actions read token missing")
    url = ("https://api.github.com/repos/" + REPOSITORY
           + "/actions/runs/" + run_id + "/approvals?per_page=100")
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ignition-eam-review-gate",
    })
    try:
        with urlopen(request, timeout=20) as response:
            require(response.status == 200, "cannot confirm review history")
            data = json.load(response)
    except (HTTPError, URLError, OSError, ValueError, TimeoutError) as exc:
        # Do not show response text, headers or credentials in CI logs.
        raise ApprovalHold("HOLD: GitHub approval API unavailable (" +
                           type(exc).__name__ + ")") from None
    return data


def verify(context, token):
    run_id = validate_context(context)
    decision = approved_review(fetch_approvals(token, run_id))
    return {"status": "APPROVED_FOR_TEST_CONTROLLER_STAGE",
            "repository": REPOSITORY,
            "release_sha": context["GITHUB_SHA"],
            "run_id": run_id,
            "run_attempt": context["GITHUB_RUN_ATTEMPT"],
            "factory": "lab-warehouse",
            "gateway": "warehouse-main",
            "project": "FactoryASmoke",
            "reviewer": decision["reviewer"],
            "environment": decision["environment"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "eam_agent_task": "NOT_AUTHORIZED",
            "production": "FORBIDDEN"}


def main():
    context = {key: os.environ.get(key, "") for key in (
        "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_EVENT_NAME",
        "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")}
    report = {"status": "HOLD_NOT_APPROVED", "environment": ENVIRONMENT,
              "reviewer": REVIEWER, "controller_stage": "NOT_RUN"}
    try:
        report = verify(context, os.environ.get("GH_APPROVAL_READ_TOKEN"))
    except ApprovalHold as exc:
        report["reason"] = str(exc)
    except Exception as exc:
        report["reason"] = "HOLD: unexpected approval validation error: " + type(exc).__name__
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "APPROVED_FOR_TEST_CONTROLLER_STAGE":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
