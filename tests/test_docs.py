"""Task 9 done-when: the docs tell a stranger what's real vs planned, and
nothing in the repo exposes a secret or an unmasked phone number."""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
README = (REPO_ROOT / "README.md").read_text()
DEMO = (REPO_ROOT / "DEMO.md").read_text()

SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),          # Google API key
    re.compile(r"EAA[0-9A-Za-z]{30,}"),               # Meta access token
    re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}"),         # Google OAuth token
    re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),        # GitHub token
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
)

# Synthetic fixture numbers may appear only in test/eval code, never in
# app code or docs (which must always use masked forms).
PHONE_PATTERN = re.compile(r"\b91[6-9]\d{9}\b")
PHONE_ALLOWED_DIRS = ("tests/", "evals/")


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return output.splitlines()


class TestReadme:
    @pytest.mark.parametrize(
        "required",
        [
            "## Architecture",
            "## Evaluation results",
            "## Implemented vs. designed for extension",
            "### Designed for extension — documented only, deliberately NOT built",
            "## Getting started",
            "Demo video",
            "Submission checklist",
            "evidence_field",
        ],
    )
    def test_required_sections_exist(self, required):
        assert required in README

    @pytest.mark.parametrize(
        "extension_item",
        [
            "Invoice generation",
            "Feedback collection",
            "Referral tracking",
            "Renewal / upsell",
            "analytics dashboard",
        ],
    )
    def test_not_built_features_are_documented_as_such(self, extension_item):
        assert extension_item in README

    def test_eval_table_is_present_with_overall_rate(self):
        assert "| **Overall** | **62** | **64** | **96.9%**" in README
        assert "not a production benchmark" in README

    def test_codex_hackathon_positioning_is_documented(self):
        assert "ChatGPT Codex Hackathon 2026" in README
        assert "Domain Agents / AI for Bharat" in README
        assert "SUBMISSION.md" in README


class TestDemoScript:
    def test_trap_question_is_the_centerpiece(self):
        assert "Does the Shela property have a private pool?" in DEMO
        assert "can't confirm" in DEMO

    def test_masking_rules_are_explicit(self):
        assert "No real phone numbers" in DEMO
        assert "mask" in DEMO.lower()

    def test_simulator_is_documented_as_not_production(self):
        assert "chat simulator" in README.lower()
        assert "production channel" in README.lower()
        assert "simulator" in DEMO.lower()


class TestNoSecretsInRepo:
    def test_no_env_or_credential_files_tracked(self):
        for path in tracked_files():
            name = Path(path).name
            assert name != ".env"
            if name != ".env.example":  # the template is meant to be tracked
                assert not name.startswith(".env."), path
            assert "credentials" not in name or name == "credentials.example.json"
            assert not name.endswith((".pem", ".key")), path

    def test_no_token_shaped_strings_in_tracked_files(self):
        for path in tracked_files():
            try:
                content = (REPO_ROOT / path).read_text()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for pattern in SECRET_PATTERNS:
                assert not pattern.search(content), f"{pattern.pattern} in {path}"

    def test_phone_literals_only_in_test_and_eval_code(self):
        for path in tracked_files():
            if path.startswith(PHONE_ALLOWED_DIRS):
                continue
            try:
                content = (REPO_ROOT / path).read_text()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            match = PHONE_PATTERN.search(content)
            assert match is None, f"unmasked number {match.group()[:4]}… in {path}"
