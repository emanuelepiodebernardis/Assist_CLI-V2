from assist.agents.diff_reviewer import (
    DiffReviewerAgent,
)

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
) -> DiffReviewerAgent:

    llm = DummyLLM(
        responses=responses
    )

    return DiffReviewerAgent(
        llm=llm
    )


def build_task() -> TaskInput:

    return TaskInput(
        command="diff",
        git_range="HEAD",
        raw_input=(
            "diff --git a/module.py b/module.py\n"
            "index 1234567..abcdefg 100644\n"
            "--- a/module.py\n"
            "+++ b/module.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def foo():\n"
            "-    return 1\n"
            "+    return 2\n"
        ),
        options={
            "impacted_files_content": {
                "module.py": (
                    "def foo():\n"
                    "    return 2\n"
                ),
            },
            "range_spec": "HEAD",
        },
    )


def build_skills() -> list[Skill]:

    return [
        Skill(
            name="diff_review_rules",
            content=(
                "Always review only changes, "
                "not unchanged code."
            ),
        )
    ]


def test_generate_draft_returns_review_text():

    agent = build_agent(
        responses=[
            (
                "## Sommario\n"
                "Il diff modifica il valore "
                "di ritorno di foo da 1 a 2.\n"
                "\n"
                "## Modifiche rilevanti\n"
                "- module.py: foo() ora "
                "ritorna 2 invece di 1.\n"
            )
        ]
    )

    result = agent.generate_draft(
        task=build_task(),
        skills=build_skills(),
    )

    # The agent returns the LLM response untouched
    assert "## Sommario" in result

    assert (
        "Modifiche rilevanti"
        in result
    )

    # Verifica che il prompt sia stato costruito
    # tramite PromptBuilder.build_diff_prompt
    assert len(agent.llm.prompts) == 1

    generated_prompt = (
        agent.llm.prompts[0]
    )

    # Il diff deve essere incluso nel prompt
    assert (
        "@@ -1,2 +1,2 @@"
        in generated_prompt
    )

    # Marcatore unico di build_diff_prompt
    assert (
        "ESEGUI ORA LA REVIEW DEL DIFF"
        in generated_prompt
    )


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

    draft = (
        "## Sommario\n"
        "Il diff modifica foo.\n"
        "\n"
        "## Modifiche rilevanti\n"
        "- module.py: cambio valore ritorno.\n"
    )

    report = agent.self_check(
        draft=draft,
        task=build_task(),
        skills=build_skills(),
    )

    # Il parsing JSON ha mappato correttamente
    # i campi del response su ValidationReport
    assert isinstance(
        report,
        ValidationReport,
    )

    assert report.is_valid is True

    assert (
        report.quality_score
        == 0.91
    )

    assert (
        report.clarity_score
        == 0.88
    )

    assert report.issues == []

    # Verifica che il prompt di self_check
    # contenga il draft
    assert len(agent.llm.prompts) == 1

    self_check_prompt = (
        agent.llm.prompts[0]
    )

    # Il draft da validare deve essere nel prompt
    assert (
        "## Sommario"
        in self_check_prompt
    )

    # Marcatore unico di
    # build_diff_self_check_prompt
    assert (
        "FOCUS SUL DIFF"
        in self_check_prompt
    )


def test_correct_returns_fixed_review():

    agent = build_agent(
        responses=[
            (
                "## Sommario\n"
                "Il diff modifica foo "
                "da 1 a 2.\n"
                "\n"
                "## Modifiche rilevanti\n"
                "- module.py:2: foo() "
                "ritorna 2 invece di 1.\n"
                "\n"
                "## Rischi\n"
                "- module.py:2: chiamanti "
                "di foo che si aspettano "
                "1 si rompono.\n"
            )
        ]
    )

    draft = (
        "## Sommario\n"
        "Il diff modifica foo.\n"
        "\n"
        "## Modifiche rilevanti\n"
        "- module.py: cambio valore ritorno.\n"
    )

    report = ValidationReport(
        is_valid=False,
        quality_score=0.4,
        clarity_score=0.5,
        issues=[],
        actions=[
            "Add risks section about callers",
        ],
    )

    corrected = agent.correct(
        draft=draft,
        report=report,
        task=build_task(),
        skills=build_skills(),
    )

    # L'output dell'LLM viene
    # ritornato non modificato
    assert "## Rischi" in corrected

    # Verifica che il prompt di correction
    # contenga draft e report
    assert len(agent.llm.prompts) == 1

    correction_prompt = (
        agent.llm.prompts[0]
    )

    # Il draft da correggere
    # deve essere nel prompt
    assert (
        "## Modifiche rilevanti"
        in correction_prompt
    )

    # L'action del report
    # deve essere nel prompt
    assert (
        "Add risks section about callers"
        in correction_prompt
    )

    # Marcatore unico di
    # build_diff_correction_prompt
    assert (
        "CORREZIONE"
        in correction_prompt
    )