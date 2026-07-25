from assist.agents.explainer import ExplainerAgent
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
) -> ExplainerAgent:

    llm = DummyLLM(
        responses=responses
    )

    return ExplainerAgent(
        llm=llm
    )


def build_task() -> TaskInput:

    return TaskInput(
        command="explain",
        file_path="math_utils.py",
        language="python",
        raw_input=(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        ),
        options={
            "depth": "brief",
        },
    )


def build_skills() -> list[Skill]:

    return [
        Skill(
            name="documentation",
            content=(
                "Spiegazioni concise, "
                "tecniche, in italiano."
            ),
        )
    ]


def test_generate_draft_returns_explanation():

    agent = build_agent(
        responses=[
            (
                "## Sommario\n\n"
                "Funzione che somma due interi "
                "e restituisce il risultato.\n"
            )
        ]
    )

    result = agent.generate_draft(
        task=build_task(),
        skills=build_skills(),
    )

    assert "## Sommario" in result
    assert "somma due interi" in result


def test_self_check_parses_validation_report():

    agent = build_agent(
        responses=[
            """
{
  "is_valid": true,
  "quality_score": 0.88,
  "clarity_score": 0.90,
  "issues": [],
  "actions": []
}
"""
        ]
    )

    report = agent.self_check(
        draft=(
            "## Sommario\n\n"
            "Funzione che somma due interi.\n"
        ),
        task=build_task(),
        skills=build_skills(),
    )

    assert isinstance(
        report,
        ValidationReport,
    )

    assert report.is_valid is True
    assert report.quality_score == 0.88
    assert report.clarity_score == 0.90
    assert report.issues == []


def test_correct_returns_fixed_explanation():

    agent = build_agent(
        responses=[
            (
                "## Sommario\n\n"
                "Funzione che somma due interi "
                "e restituisce il risultato.\n\n"
                "## Struttura\n\n"
                "Prende due parametri di tipo int "
                "e restituisce la loro somma.\n"
            )
        ]
    )

    report = ValidationReport(
        is_valid=False,
        quality_score=0.4,
        clarity_score=0.5,
        issues=[],
        actions=[
            "Aggiungere sezione Struttura",
        ],
    )

    corrected = agent.correct(
        draft=(
            "## Sommario\n\n"
            "Funzione che somma due interi.\n"
        ),
        report=report,
        task=build_task(),
        skills=build_skills(),
    )

    assert "## Struttura" in corrected