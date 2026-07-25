from assist.agents.test_generator import (
    TestGeneratorAgent,
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
) -> TestGeneratorAgent:

    llm = DummyLLM(
        responses=responses
    )

    return TestGeneratorAgent(
        llm=llm
    )


def build_task() -> TaskInput:

    return TaskInput(
        command="test",
        file_path="math_utils.py",
        language="python",
        raw_input=(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        ),
        options={},
    )


def build_skills() -> list[Skill]:

    return [
        Skill(
            name="pytest_rules",
            content=(
                "Always generate pytest "
                "tests with type hints "
                "and Arrange-Act-Assert."
            ),
        )
    ]


def test_generate_draft_returns_pytest_code():

    agent = build_agent(
        responses=[
            (
                "import pytest\n"
                "\n"
                "\n"
                "def test_add_happy_path():\n"
                "    assert add(1, 2) == 3\n"
            )
        ]
    )

    result = agent.generate_draft(
        task=build_task(),
        skills=build_skills(),
    )

    # The agent returns the LLM response untouched
    assert "def test_" in result
    assert "assert add(1, 2) == 3" in result

    # Verifica che il prompt sia stato costruito tramite
    # PromptBuilder.build_test_prompt (e non un altro builder)
    assert len(agent.llm.prompts) == 1

    generated_prompt = agent.llm.prompts[0]

    # Il prompt deve contenere il codice originale del file target
    assert (
        "def add(a: int, b: int) -> int:"
        in generated_prompt
    )

    # Marcatore unico di build_test_prompt
    # (presente solo in quel metodo del PromptBuilder)
    assert (
        "GENERA ORA I TEST PYTEST"
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
        "import pytest\n"
        "\n"
        "\n"
        "def test_add_happy_path():\n"
        "    assert add(1, 2) == 3\n"
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
    assert report.quality_score == 0.91
    assert report.clarity_score == 0.88
    assert report.issues == []

    # Verifica che il prompt di self_check contenga il draft
    assert len(agent.llm.prompts) == 1

    self_check_prompt = agent.llm.prompts[0]

    # Il draft da validare deve essere nel prompt
    assert (
        "def test_add_happy_path"
        in self_check_prompt
    )

    # Marcatore unico di build_test_self_check_prompt
    assert "VALIDAZIONE" in self_check_prompt


def test_correct_returns_fixed_tests():

    agent = build_agent(
        responses=[
            (
                "import pytest\n"
                "\n"
                "\n"
                "def test_add_edge_case():\n"
                "    assert add(0, 0) == 0\n"
            )
        ]
    )

    draft = (
        "import pytest\n"
        "\n"
        "\n"
        "def test_add_happy_path():\n"
        "    assert add(1, 2) == 3\n"
    )

    report = ValidationReport(
        is_valid=False,
        quality_score=0.4,
        clarity_score=0.5,
        issues=[],
        actions=[
            "Add edge case coverage",
        ],
    )

    corrected = agent.correct(
        draft=draft,
        report=report,
        task=build_task(),
        skills=build_skills(),
    )

    # L'output dell'LLM viene ritornato non modificato
    assert "test_add_edge_case" in corrected

    # Verifica che il prompt di correction
    # contenga draft e report
    assert len(agent.llm.prompts) == 1

    correction_prompt = agent.llm.prompts[0]

    # Il draft da correggere deve essere nel prompt
    assert (
        "def test_add_happy_path"
        in correction_prompt
    )

    # L'azione richiesta dal report deve essere nel prompt
    assert (
        "Add edge case coverage"
        in correction_prompt
    )

    # Marcatore unico di build_test_correction_prompt
    assert "CORREZIONE" in correction_prompt