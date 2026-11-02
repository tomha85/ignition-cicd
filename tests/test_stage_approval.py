"""Verify that EAM Controller staging cannot bypass manual GitHub approval."""
import unittest
from unittest.mock import patch
from scripts import verify_stage_approval as a

CTX = {
    "GITHUB_REPOSITORY": "tomha85/ignition-cicd",
    "GITHUB_REF": "refs/heads/feat/reusable-multifactory-framework-v1",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_RUN_ID": "1234",
    "GITHUB_RUN_ATTEMPT": "1",
}
REVIEW = {"state":"approved","user":{"login":"tomha85"},
          "environments":[{"name":"ignition-test"}]}

class ApprovalVerificationTests(unittest.TestCase):
    def test_valid_review_authorizes_current_run_only(self):
        with patch.object(a, "fetch_approvals", return_value=[REVIEW]) as fetch:
            record = a.verify(dict(CTX), "token-not-logged")
        fetch.assert_called_once_with("token-not-logged", "1234")
        self.assertEqual(record["status"],"APPROVED_FOR_TEST_CONTROLLER_STAGE")
        self.assertEqual(record["reviewer"],"tomha85")

    def test_no_approval_fails_closed(self):
        with self.assertRaisesRegex(a.ApprovalHold,"NO approval"):
            a.approved_review([])

    def test_another_user_cannot_approve(self):
        with self.assertRaisesRegex(a.ApprovalHold,"NO approval"):
            a.approved_review([{"state":"approved","user":{"login":"other"},
                                "environments":[{"name":"ignition-test"}]}])

    def test_other_environment_cannot_approve(self):
        with self.assertRaisesRegex(a.ApprovalHold,"NO approval"):
            a.approved_review([{"state":"approved","user":{"login":"tomha85"},
                                "environments":[{"name":"production"}]}])

    def test_rejected_or_bypassed_not_approval(self):
        for state in ("rejected","pending","bypassed"):
            with self.subTest(state=state), self.assertRaises(a.ApprovalHold):
                a.approved_review([{"state":state,"user":{"login":"tomha85"},
                                    "environments":[{"name":"ignition-test"}]}])

    def test_reruns_cannot_reuse_prior_approval(self):
        ctx=dict(CTX,GITHUB_RUN_ATTEMPT="2")
        with self.assertRaisesRegex(a.ApprovalHold,"fresh workflow run"):
            a.validate_context(ctx)

    def test_wrong_branch_production_forbidden(self):
        ctx=dict(CTX,GITHUB_REF="refs/heads/main")
        with self.assertRaises(a.ApprovalHold):
            a.validate_context(ctx)

    def test_wrong_repo_forbidden(self):
        with self.assertRaises(a.ApprovalHold):
            a.validate_context(dict(CTX,GITHUB_REPOSITORY="other/ignition-cicd"))

    def test_reject_pull_request_event(self):
        with self.assertRaises(a.ApprovalHold):
            a.validate_context(dict(CTX,GITHUB_EVENT_NAME="pull_request"))

    def test_real_controller_stager_enforces_approval_before_mutation(self):
        from pathlib import Path
        source = Path("scripts/factory_a_controller_smoke.py").read_text()
        self.assertIn("verify_github_approval(os.environ", source)
        self.assertLess(source.index("verify_github_approval(os.environ"),
                        source.index('backup.mkdir(mode=0o700)'))

    def test_missing_token_blocks_api_call(self):
        with self.assertRaisesRegex(a.ApprovalHold,"read token missing"):
            a.fetch_approvals("", "1234")

if __name__=="__main__":
    unittest.main()
