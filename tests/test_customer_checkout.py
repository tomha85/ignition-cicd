"""Source SHA provenance checks, with Git subprocess fully mocked."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from reusable_cicd.core import FrameworkError
from scripts.verify_customer_checkout import verify_checkout

SHA = "d" * 40


class FakeResult:
    def __init__(self, stdout):
        self.stdout = stdout


class VerifyCustomerCheckoutTests(unittest.TestCase):
    def test_clean_exact_checkout_returns_source_only_evidence(self):
        commands = []

        def git(args, **kwargs):
            commands.append(args)
            if "rev-parse" in args:
                return FakeResult(SHA + "\n")
            return FakeResult("")

        with tempfile.TemporaryDirectory() as temporary:
            report = verify_checkout(Path(temporary), SHA, runner=git)
        self.assertEqual(report["checkout_commit"], "VERIFIED")
        self.assertTrue(report["customer_source_clean"])
        self.assertEqual(report["production"], "HOLD")
        self.assertEqual(len(commands), 2)
        self.assertIn("factories", commands[1])
        self.assertIn("config", commands[1])
        self.assertIn("scripts", commands[1])

    def test_wrong_head_fails_closed(self):
        def git(args, **kwargs):
            return FakeResult("e" * 40 + "\n" if "rev-parse" in args else "")

        with self.assertRaisesRegex(FrameworkError, "does not match"):
            verify_checkout(Path("."), SHA, runner=git)

    def test_modified_or_untracked_source_fails_closed(self):
        def git(args, **kwargs):
            if "rev-parse" in args:
                return FakeResult(SHA + "\n")
            return FakeResult("?? factories/new-customer/projects/NotCommitted/view.json\n")

        with self.assertRaisesRegex(FrameworkError, "modified or untracked"):
            verify_checkout(Path("."), SHA, runner=git)

    def test_invalid_sha_fails_before_git(self):
        def should_not_run(*args, **kwargs):
            self.fail("Git must not be called for invalid SHA")

        with self.assertRaisesRegex(FrameworkError, "40-hex"):
            verify_checkout(Path("."), "abc", runner=should_not_run)

    def test_git_failure_fails_closed(self):
        def git(args, **kwargs):
            raise subprocess.CalledProcessError(128, args)

        with self.assertRaisesRegex(FrameworkError, "cannot inspect"):
            verify_checkout(Path("."), SHA, runner=git)


if __name__ == "__main__":
    unittest.main()
