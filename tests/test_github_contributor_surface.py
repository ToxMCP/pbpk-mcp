from pathlib import Path
import unittest


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


class GitHubContributorSurfaceTests(unittest.TestCase):
    def test_required_contributor_files_exist(self) -> None:
        required = [
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
            "CHANGELOG.md",
            ".github/CODEOWNERS",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/bug_report.md",
            ".github/ISSUE_TEMPLATE/docs_or_reviewability.md",
            "docs/release_readiness.md",
            "docs/github_branch_protection.md",
            "docs/deployment/s3_object_lock_audit.md",
        ]
        missing = [path for path in required if not (WORKSPACE_ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_contributing_includes_setup_and_common_checks(self) -> None:
        content = (WORKSPACE_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("## Local Setup", content)
        self.assertIn("## Common Checks", content)
        self.assertIn("make runtime-contract-test", content)
        self.assertIn("docs/release_readiness.md", content)
        self.assertIn("docs/github_branch_protection.md", content)
        self.assertIn("docs/deployment/s3_object_lock_audit.md", content)
        self.assertIn(".github/CODEOWNERS", content)

    def test_codeowners_designates_senseibelbi(self) -> None:
        content = (WORKSPACE_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertIn("* @senseibelbi", content)

    def test_readme_points_to_contributing_and_security_docs(self) -> None:
        content = (WORKSPACE_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("CONTRIBUTING.md", content)
        self.assertIn("SECURITY.md", content)
        self.assertIn("docs/github_branch_protection.md", content)
        self.assertIn("docs/deployment/s3_object_lock_audit.md", content)


if __name__ == "__main__":
    unittest.main()
