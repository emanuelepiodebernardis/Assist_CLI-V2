"""Characterization tests for PromptBuilder.

Capture the structural behavior of the 21 build_*_prompt methods as a safety
net for the upcoming Epic 1.2 refactor (PromptBuilder dichiarativo).

The tests are intentionally structural (assert on sections, markers, payload
positioning), not literal: small textual tweaks must not break the suite.
What MUST break the suite is the loss of a section, a misplaced payload, or
the disappearance of a task-specific instruction.

Coverage:
- 21 (task x stage) combinations: structural invariants common to all
- task-specific markers: each task asserts on its own characteristic strings
- error paths: methods that raise ValueError on missing raw_input
"""

from __future__ import annotations

import pytest

from assist.core.prompt_builder import PromptBuilder
from assist.schemas.models import (
    Issue,
    Skill,
    TaskInput,
    ValidationReport,
)


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
def skills() -> list[Skill]:
    """Two minimal skills with distinctive content for membership checks."""
    return [
        Skill(
            name="project_rules",
            content="SKILL_PROJECT_RULES_MARKER: always write clean code.",
        ),
        Skill(
            name="code_review",
            content="SKILL_CODE_REVIEW_MARKER: review the code carefully.",
        ),
    ]


@pytest.fixture
def report() -> ValidationReport:
    """Validation report with one critical issue, used for correction prompts."""
    return ValidationReport(
        is_valid=False,
        quality_score=0.55,
        clarity_score=0.60,
        issues=[
            Issue(
                severity="critical",
                message="REPORT_ISSUE_MARKER: missing type hints",
                location="line 5",
            ),
        ],
        actions=["Add type hints to all public functions"],
    )


def _task(
    command: str,
    raw_input: str | None = "PAYLOAD_MARKER: x = 42",
    options: dict | None = None,
    file_path: str = "test.py",
) -> TaskInput:
    """Build a TaskInput for the given command with sensible defaults."""
    return TaskInput(
        command=command,
        file_path=file_path,
        raw_input=raw_input,
        options=options or {},
    )


DRAFT_MARKER = "DRAFT_MARKER: this is the previously generated draft."


# ────────────────────────────────────────────────────────────────────────
# Original test (preserved for backward compatibility)
# ────────────────────────────────────────────────────────────────────────


def test_build_review_prompt_includes_code():
    task = TaskInput(
        command="review",
        file_path="test.py",
        raw_input="print('hello')",
    )

    skills = [
        Skill(
            name="project_rules",
            content="Always write clean code.",
        )
    ]

    prompt = PromptBuilder.build_review_prompt(
        task=task,
        skills=skills,
    )

    assert "print('hello')" in prompt
    assert "Always write clean code." in prompt


# ────────────────────────────────────────────────────────────────────────
# Structural invariants — common to all 21 methods
# ────────────────────────────────────────────────────────────────────────
# Each prompt must include:
# 1. Both skill contents (skills block at the top)
# 2. The "# CONTESTO STRUTTURALE" section header
# 3. The relevant payload (raw_input for draft, draft for self_check/correct,
#    report for correct)


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_draft_prompt_includes_skills(command: str, skills: list[Skill]):
    """Each draft prompt must inject both skill contents."""
    method = _draft_method_for(command)
    task = _task_for_command(command)
    prompt = method(task=task, skills=skills)

    assert "SKILL_PROJECT_RULES_MARKER" in prompt
    assert "SKILL_CODE_REVIEW_MARKER" in prompt


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_draft_prompt_includes_context_section(
    command: str, skills: list[Skill]
):
    """Each draft prompt must include the structural context section header."""
    method = _draft_method_for(command)
    task = _task_for_command(command)
    prompt = method(task=task, skills=skills)

    assert "CONTESTO STRUTTURALE" in prompt


@pytest.mark.parametrize(
    "command",
    # 'repo' has no raw_input payload (it analyzes the whole repository
    # via context, not a single file). Exclude it from this check.
    ["review", "generate", "refactor", "explain", "test", "diff"],
)
def test_draft_prompt_includes_payload(command: str, skills: list[Skill]):
    """Each draft prompt (except repo) must include the raw_input payload."""
    method = _draft_method_for(command)
    task = _task_for_command(command)
    prompt = method(task=task, skills=skills)

    assert "PAYLOAD_MARKER" in prompt


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_self_check_prompt_includes_skills(
    command: str, skills: list[Skill]
):
    """Each self_check prompt must inject both skill contents."""
    method = _self_check_method_for(command)
    task = _task_for_command(command)
    prompt = method(draft=DRAFT_MARKER, task=task, skills=skills)

    assert "SKILL_PROJECT_RULES_MARKER" in prompt
    assert "SKILL_CODE_REVIEW_MARKER" in prompt


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_self_check_prompt_includes_draft(
    command: str, skills: list[Skill]
):
    """Each self_check prompt must include the draft to be validated."""
    method = _self_check_method_for(command)
    task = _task_for_command(command)
    prompt = method(draft=DRAFT_MARKER, task=task, skills=skills)

    assert "DRAFT_MARKER" in prompt


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_correct_prompt_includes_skills(
    command: str, skills: list[Skill], report: ValidationReport
):
    """Each correct prompt must inject both skill contents."""
    method = _correct_method_for(command)
    task = _task_for_command(command)
    prompt = method(draft=DRAFT_MARKER, report=report, task=task, skills=skills)

    assert "SKILL_PROJECT_RULES_MARKER" in prompt
    assert "SKILL_CODE_REVIEW_MARKER" in prompt


@pytest.mark.parametrize(
    "command",
    ["review", "generate", "refactor", "explain", "test", "diff", "repo"],
)
def test_correct_prompt_includes_draft_and_report(
    command: str, skills: list[Skill], report: ValidationReport
):
    """Each correct prompt must include both the draft and the report."""
    method = _correct_method_for(command)
    task = _task_for_command(command)
    prompt = method(draft=DRAFT_MARKER, report=report, task=task, skills=skills)

    assert "DRAFT_MARKER" in prompt
    # The report is serialized as JSON; assert one of its fields is present.
    assert "REPORT_ISSUE_MARKER" in prompt


# ────────────────────────────────────────────────────────────────────────
# Task-specific markers — each task has its own characteristic strings
# ────────────────────────────────────────────────────────────────────────
# These tests assert on the task-specific closing instructions: if a refactor
# turns "## Sommario" into "## Summary" by accident, these tests catch it.


def test_review_prompt_mentions_sommario_marker(skills: list[Skill]):
    task = _task("review")
    prompt = PromptBuilder.build_review_prompt(task=task, skills=skills)
    assert "## Sommario" in prompt


def test_generate_prompt_mentions_language_constraint(skills: list[Skill]):
    task = _task("generate", options={"prompt": "Generate a function"})
    prompt = PromptBuilder.build_generate_prompt(task=task, skills=skills)
    assert "SOLO codice" in prompt
    assert "python" in prompt.lower()


def test_refactor_prompt_mentions_behavioral_invariant(skills: list[Skill]):
    task = _task("refactor")
    prompt = PromptBuilder.build_refactor_prompt(task=task, skills=skills)
    assert "comportamento osservabile" in prompt.lower()
    assert "## Codice refactorizzato" in prompt


def test_explain_prompt_mentions_explanation_task(skills: list[Skill]):
    task = _task("explain")
    prompt = PromptBuilder.build_explain_prompt(task=task, skills=skills)
    # Explain prompt must reference the explanation task or "spiega" keyword.
    assert (
        "spieg" in prompt.lower() or "explain" in prompt.lower()
    )


def test_test_prompt_mentions_pytest(skills: list[Skill]):
    task = _task("test")
    prompt = PromptBuilder.build_test_prompt(task=task, skills=skills)
    assert "pytest" in prompt.lower()


def test_diff_prompt_mentions_diff_review_format(skills: list[Skill]):
    task = _task("diff", options={"range_spec": "HEAD~3..HEAD"})
    prompt = PromptBuilder.build_diff_prompt(task=task, skills=skills)
    assert "## Sommario" in prompt
    assert "## Modifiche rilevanti" in prompt
    assert "HEAD~3..HEAD" in prompt


def test_repo_prompt_mentions_repository_overview_sections(
    skills: list[Skill],
):
    # repo has no raw_input; the task is identified by repo_path
    task = TaskInput(
        command="repo",
        file_path=None,
        raw_input=None,
        repo_path="/path/to/repo",
        options={},
    )
    prompt = PromptBuilder.build_repo_prompt(task=task, skills=skills)
    assert "## Panoramica" in prompt
    assert "## Architettura" in prompt
    assert "## Salute del codice" in prompt
    assert "/path/to/repo" in prompt


# ────────────────────────────────────────────────────────────────────────
# Error paths
# ────────────────────────────────────────────────────────────────────────
# Some draft methods raise ValueError if raw_input is missing. Codify the
# current behavior: review, refactor, diff explicitly check; the rest do
# not (this is a hidden inconsistency that the refactor might unify, but
# we record it as-is).


@pytest.mark.parametrize(
    "command,method_name",
    [
        ("review", "build_review_prompt"),
        ("refactor", "build_refactor_prompt"),
        ("diff", "build_diff_prompt"),
    ],
)
def test_draft_raises_on_missing_raw_input(
    command: str, method_name: str, skills: list[Skill]
):
    """review/refactor/diff explicitly require raw_input."""
    task = _task(command, raw_input=None)
    method = getattr(PromptBuilder, method_name)
    with pytest.raises(ValueError, match="raw_input"):
        method(task=task, skills=skills)


# ────────────────────────────────────────────────────────────────────────
# Structural invariants — order of major sections
# ────────────────────────────────────────────────────────────────────────
# Skills block comes first, then context, then payload, then closing
# instructions. Verify the ordering relationship between markers.


def test_review_prompt_order_skills_before_payload(skills: list[Skill]):
    task = _task("review")
    prompt = PromptBuilder.build_review_prompt(task=task, skills=skills)
    # Skills block must appear before the code payload in the prompt.
    assert prompt.index("SKILL_PROJECT_RULES_MARKER") < prompt.index(
        "PAYLOAD_MARKER"
    )


def test_review_self_check_order_skills_before_draft(skills: list[Skill]):
    task = _task("review")
    prompt = PromptBuilder.build_self_check_prompt(
        draft=DRAFT_MARKER, task=task, skills=skills
    )
    assert prompt.index("SKILL_PROJECT_RULES_MARKER") < prompt.index(
        "DRAFT_MARKER"
    )


def test_review_correct_order_draft_before_report(
    skills: list[Skill], report: ValidationReport
):
    task = _task("review")
    prompt = PromptBuilder.build_correction_prompt(
        draft=DRAFT_MARKER, report=report, task=task, skills=skills
    )
    assert prompt.index("DRAFT_MARKER") < prompt.index("REPORT_ISSUE_MARKER")


# ────────────────────────────────────────────────────────────────────────
# Context block — render is plumbed correctly when options carry context
# ────────────────────────────────────────────────────────────────────────
# When task.options contains structural context dicts, they must surface
# in the rendered prompt. This guards against accidental decoupling.


def test_review_prompt_renders_options_context(skills: list[Skill]):
    task = _task(
        "review",
        options={
            "semantic_context": {
                "functions": ["SEMANTIC_CTX_MARKER"],
            },
        },
    )
    prompt = PromptBuilder.build_review_prompt(task=task, skills=skills)
    assert "SEMANTIC_CTX_MARKER" in prompt
    # The context block uses "## Semantic Context" as section header.
    assert "Semantic Context" in prompt


def test_repo_prompt_renders_repository_context(skills: list[Skill]):
    task = TaskInput(
        command="repo",
        file_path=None,
        raw_input=None,
        repo_path="/some/repo",
        options={
            "repository_context": {
                "project_size": "REPOSITORY_SIZE_MARKER",
            },
        },
    )
    prompt = PromptBuilder.build_repo_prompt(task=task, skills=skills)
    assert "REPOSITORY_SIZE_MARKER" in prompt
    assert "Repository Context" in prompt


# ────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────


def _draft_method_for(command: str):
    """Return the build_*_prompt (draft) method for a given command."""
    mapping = {
        "review": PromptBuilder.build_review_prompt,
        "generate": PromptBuilder.build_generate_prompt,
        "refactor": PromptBuilder.build_refactor_prompt,
        "explain": PromptBuilder.build_explain_prompt,
        "test": PromptBuilder.build_test_prompt,
        "diff": PromptBuilder.build_diff_prompt,
        "repo": PromptBuilder.build_repo_prompt,
    }
    return mapping[command]


def _self_check_method_for(command: str):
    """Return the build_*_self_check_prompt method for a given command."""
    mapping = {
        # review uses 'build_self_check_prompt' (no task prefix); others
        # use 'build_<task>_self_check_prompt'.
        "review": PromptBuilder.build_self_check_prompt,
        "generate": PromptBuilder.build_generate_self_check_prompt,
        "refactor": PromptBuilder.build_refactor_self_check_prompt,
        "explain": PromptBuilder.build_explain_self_check_prompt,
        "test": PromptBuilder.build_test_self_check_prompt,
        "diff": PromptBuilder.build_diff_self_check_prompt,
        "repo": PromptBuilder.build_repo_self_check_prompt,
    }
    return mapping[command]


def _correct_method_for(command: str):
    """Return the build_*_correction_prompt method for a given command."""
    mapping = {
        # Same asymmetry as above: review uses 'build_correction_prompt'.
        "review": PromptBuilder.build_correction_prompt,
        "generate": PromptBuilder.build_generate_correction_prompt,
        "refactor": PromptBuilder.build_refactor_correction_prompt,
        "explain": PromptBuilder.build_explain_correction_prompt,
        "test": PromptBuilder.build_test_correction_prompt,
        "diff": PromptBuilder.build_diff_correction_prompt,
        "repo": PromptBuilder.build_repo_correction_prompt,
    }
    return mapping[command]


def _task_for_command(command: str) -> TaskInput:
    """Build a TaskInput appropriate for the given command.

    Repo has no raw_input; the others have a payload marker.
    """
    if command == "repo":
        return TaskInput(
            command="repo",
            file_path=None,
            raw_input=None,
            repo_path="/path/to/repo",
            options={},
        )
    if command == "diff":
        return _task("diff", options={"range_spec": "HEAD~1..HEAD"})
    return _task(command)