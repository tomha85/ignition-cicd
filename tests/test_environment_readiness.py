"""Readiness must skip cleanly if GitHub review protection is unavailable."""
import unittest
from unittest.mock import patch, MagicMock
from scripts import check_environment_reviewers as a

RULE={"name":"ignition-test","protection_rules":[
    {"type":"required_reviewers","prevent_self_review":False,"reviewers":[
        {"type":"User","reviewer":{"login":"tomha85"}}]}]}
REPO="tomha85/ignition-cicd"
BRANCH="refs/heads/feat/reusable-multifactory-framework-v1"

class ReviewerReadinessTests(unittest.TestCase):
    def test_verified_required_reviewer(self):
        self.assertTrue(a.is_required_reviewer_enabled(RULE))
    def test_missing_reviewer(self):
        self.assertFalse(a.is_required_reviewer_enabled({"name":"ignition-test","protection_rules":[]}))
    def test_wrong_reviewer(self):
        wrong={"name":"ignition-test","protection_rules":[{"type":"required_reviewers",
                "reviewers":[{"type":"User","reviewer":{"login":"another"}}]}]}
        self.assertFalse(a.is_required_reviewer_enabled(wrong))
    def test_self_review_prevented(self):
        blocked={"name":"ignition-test","protection_rules":[{"type":"required_reviewers",
                "prevent_self_review":True,
                "reviewers":[{"type":"User","reviewer":{"login":"tomha85"}}]}]}
        self.assertFalse(a.is_required_reviewer_enabled(blocked))
    def test_wrong_environment(self):
        self.assertFalse(a.is_required_reviewer_enabled(dict(RULE,name="production")))
    def test_wrong_repo_is_skip(self):
        self.assertFalse(a.inspect("token","other/repo",BRANCH)["ready"])
    def test_missing_token_is_clean_skip(self):
        state=a.inspect("",REPO,BRANCH)
        self.assertEqual(state["status"],"APPROVAL_SETUP_REQUIRED")
        self.assertEqual(state["reason"],"GITHUB_READ_TOKEN_MISSING")
    def test_api_failure_is_clean_skip(self):
        with patch.object(a,"urlopen",side_effect=OSError("network")):
            result=a.inspect("token",REPO,BRANCH)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"],"ENVIRONMENT_REVIEW_RULE_NOT_VERIFIED")
    def test_valid_api_response_is_ready(self):
        response=MagicMock()
        response.status=200
        response.__enter__.return_value=response
        with patch.object(a,"urlopen",return_value=response),patch.object(a.json,"load",return_value=RULE):
            result=a.inspect("token",REPO,BRANCH)
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"],"NATIVE_GITHUB_REVIEWER_GATE_CONFIGURED")

if __name__=="__main__":
    unittest.main()
