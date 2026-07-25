from assist.agents.generator import GeneratorAgent
from assist.schemas.models import (
    Skill,
    TaskInput,
    ValidationReport,
)


class DummyLLM:

    def __init__(
        self,
        responses: list[str],
    ) -> None:

        self.responses = responses
        self.prompts: list[str] = []

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:

        self.prompts.append(prompt)

        if not self.responses:
            raise AssertionError(
                "LLM called too many times"
            )

        return self.responses.pop(0)


def build_agent(
    responses: list[str],
) -> GeneratorAgent:

    llm = DummyLLM(
        responses=responses
    )

    return GeneratorAgent(
        llm=llm
    )


def build_task() -> TaskInput:

    return TaskInput(
        command="generate",
        file_path="math_utils.py",
        language="python",
        options={
            "prompt": (
                "Create a function "
                "that adds two integers."
            )
        },
    )


def build_skills() -> list[Skill]:

    return [
        Skill(
            name="python_rules",
            content=(
                "Always use type hints "
                "and docstrings."
            ),
        )
    ]


def test_generate_draft_returns_code():

    agent = build_agent(
        responses=[
            (
                "def add(a: int, b: int) -> int:\n"
                '    """Add two integers."""\n'
                "    return a + b\n"
            )
        ]
    )

    result = agent.generate_draft(
        task=build_task(),
        skills=build_skills(),
    )

    assert "def add" in result
    assert "return a + b" in result


def test_self_check_parses_validation_report():

    agent = build_agent(
        responses=[
            """
{
  "is_valid": true,
  "quality_score": 0.91,
  "clarity_score": 0.88,
  "issues": [],
  "actions": []
}
"""
        ]
    )

    report = agent.self_check(
        draft=(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        ),
        task=build_task(),
        skills=build_skills(),
    )

    assert isinstance(
        report,
        ValidationReport,
    )

    assert report.is_valid is True
    assert report.quality_score == 0.91
    assert report.clarity_score == 0.88
    assert report.issues == []


def test_correct_returns_fixed_code():

    agent = build_agent(
        responses=[
            (
                "def add(a: int, b: int) -> int:\n"
                '    """Add two integers."""\n'
                "    return a + b\n"
            )
        ]
    )

    report = ValidationReport(
        is_valid=False,
        quality_score=0.4,
        clarity_score=0.5,
        issues=[],
        actions=[
            "Add docstring",
        ],
    )

    corrected = agent.correct(
        draft=(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        ),
        report=report,
        task=build_task(),
        skills=build_skills(),
    )

    assert '"""Add two integers."""' in corrected