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

    def test_production_branch_still_forbidden(self):
        ctx=dict(CTX,GITHUB_REF="refs/heads/production")
        with self.assertRaises(a.ApprovalHold):
            a.validate_context(ctx)

    def test_main_allowed_with_fresh_run_approval(self):
        ctx=dict(CTX,GITHUB_REF="refs/heads/main")
        self.assertEqual(a.validate_context(ctx),"1234")

    def test_main_workflows_still_require_review(self):
        from pathlib import Path
        for path in (".github/workflows/factory-a-controller-smoke.yml",
                     ".github/workflows/reusable-deploy.yml",
                     ".github/workflows/ignition-eam-multi-factory.yml"):
            text=Path(path).read_text()
            self.assertIn("refs/heads/main",text)
        for path in (".github/workflows/factory-a-controller-smoke.yml",
                     ".github/workflows/reusable-deploy.yml"):
            content=Path(path).read_text()
            self.assertIn("environment: ignition-test",content)
            self.assertIn("scripts/verify_stage_approval.py",content)


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
        self.assertIn('out("git", "rev-parse", "HEAD")==a.sha', source)
        self.assertLess(source.index("verify_github_approval(os.environ"),
                        source.index('backup.mkdir(mode=0o700)'))

    def test_smoke_workflow_waits_after_validation_and_checks_real_review(self):
        from pathlib import Path
        text = Path(".github/workflows/factory-a-controller-smoke.yml").read_text()
        stage = text.split("  stage-controller:",1)[1]
        self.assertIn("needs: validate", stage)
        self.assertIn("environment: ignition-test", stage)
        self.assertIn("GH_APPROVAL_READ_TOKEN: ${{ github.token }}", stage)
        self.assertLess(stage.index("scripts/verify_stage_approval.py"),
                        stage.index("scripts/factory_a_controller_smoke.py --stage-controller"))

    def test_reusable_workflow_has_same_protection(self):
        from pathlib import Path
        text = Path(".github/workflows/reusable-deploy.yml").read_text()
        stage = text.split("  stage-controller:",1)[1]
        self.assertIn("needs: select-and-validate", stage)
        self.assertIn("environment: ignition-test", stage)
        self.assertIn("GH_APPROVAL_READ_TOKEN: ${{ github.token }}", stage)
        self.assertLess(stage.index("scripts/verify_stage_approval.py"),
                        stage.index("--action stage-controller"))

    def test_legacy_unreviewed_write_actions_removed(self):
        from pathlib import Path
        text = Path(".github/workflows/ignition-eam-multi-factory.yml").read_text()
        self.assertNotIn("options:", text)
        self.assertEqual(text.split("permissions:",1)[0].count("        type: string"), 2)
        self.assertNotIn("options: [framework-validate, framework-stage-controller]", text)
        self.assertIn("needs: validate", text)
        self.assertIn("environment: ignition-test", text)
        self.assertIn("scripts/verify_stage_approval.py", text)
        self.assertIn("needs.validate.outputs.stage_eligible == 'true'", text)
        self.assertIn("evidence/selected-controller-stage.json", text)
        self.assertNotIn("uses: ./.github/workflows/deploy-test.yml", text)

    def test_exactly_two_jobs_and_native_environment_gate(self):
        from pathlib import Path
        expected = {
            ".github/workflows/factory-a-controller-smoke.yml":
                ["validate", "stage-controller"],
            ".github/workflows/reusable-deploy.yml":
                ["select-and-validate", "stage-controller"],
        }
        for path, names in expected.items():
            source = Path(path).read_text()
            # exactly two unindented job keys underneath jobs:
            jobs = [line.strip()[:-1]
                    for line in source.split("jobs:", 1)[1].splitlines()
                    if line.startswith("  ") and not line.startswith("   ")
                    and line.rstrip().endswith(":")]
            self.assertEqual(jobs, names, path)
            self.assertNotIn("  reviewer-readiness:", source)
            stage = source.split("  stage-controller:", 1)[1]
            self.assertIn("needs: " + names[0], stage)
            self.assertIn("environment: ignition-test", stage)

    def test_missing_token_blocks_api_call(self):
        with self.assertRaisesRegex(a.ApprovalHold,"read token missing"):
            a.fetch_approvals("", "1234")

if __name__=="__main__":
    unittest.main()
