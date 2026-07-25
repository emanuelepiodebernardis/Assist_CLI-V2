from assist.agents.repo_agent import (
    RepoAgent,
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
) -> RepoAgent:

    llm = DummyLLM(
        responses=responses
    )

    return RepoAgent(
        llm=llm
    )


def build_task() -> TaskInput:

    return TaskInput(
        command="repo",
        repo_path=".",
        language="python",
        options={},
    )


def build_skills() -> list[Skill]:

    return [
        Skill(
            name="repository_overview",
            content=(
                "Produce a repository overview "
                "anchored to context data. "
                "No invented architectural patterns."
            ),
        )
    ]


def test_generate_draft_returns_overview_markdown():

    agent = build_agent(
        responses=[
            (
                "## Panoramica\n"
                "Il repository contiene 23 file Python "
                "organizzati in 5 sotto-pacchetti.\n\n"
                "## Architettura\n"
                "Nessun ciclo di import rilevato. "
                "Health score: 0.92.\n\n"
                "## Salute del codice\n"
                "2 god class, 5 long method, "
                "3 complexity warning.\n"
            )
        ]
    )

    result = agent.generate_draft(
        task=build_task(),
        skills=build_skills(),
    )

    # The agent returns the LLM response untouched
    assert "## Panoramica" in result
    assert "## Architettura" in result
    assert "## Salute del codice" in result

    # Verifica che il prompt sia stato costruito tramite
    # PromptBuilder.build_repo_prompt (e non un altro builder)
    assert len(agent.llm.prompts) == 1

    generated_prompt = agent.llm.prompts[0]

    # Il prompt deve contenere il repo_path del task
    assert "Path: ." in generated_prompt

    # Marcatore unico di build_repo_prompt
    # (presente solo in quel metodo del PromptBuilder)
    assert (
        "ESEGUI ORA L'OVERVIEW"
        in generated_prompt
    )


def test_self_check_parses_validation_report():

    agent = build_agent(
        responses=[
            """
{
  "is_valid": true,
  "quality_score": 0.88,
  "clarity_score": 0.85,
  "issues": [],
  "actions": []
}
"""
        ]
    )

    draft = (
        "## Panoramica\n"
        "Repository di 23 file Python.\n\n"
        "## Architettura\n"
        "Health score: 0.92.\n\n"
        "## Salute del codice\n"
        "2 god class identificate.\n"
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
    assert report.quality_score == 0.88
    assert report.clarity_score == 0.85
    assert report.issues == []

    # Verifica che il prompt di self_check contenga il draft
    assert len(agent.llm.prompts) == 1

    self_check_prompt = agent.llm.prompts[0]

    # Il draft da validare deve essere nel prompt
    assert (
        "Repository di 23 file Python"
        in self_check_prompt
    )

    # Marcatore unico di build_repo_self_check_prompt
    assert (
        "OVERVIEW DA VALIDARE"
        in self_check_prompt
    )


def test_correct_returns_fixed_overview():

    agent = build_agent(
        responses=[
            (
                "## Panoramica\n"
                "Il repository contiene 23 file Python.\n\n"
                "## Architettura\n"
                "Nessun ciclo di import. Health score: 0.92.\n\n"
                "## Salute del codice\n"
                "2 god class, 5 long method.\n"
            )
        ]
    )

    draft = (
        "## Panoramica\n"
        "Il progetto e' ben strutturato e segue "
        "Clean Architecture.\n\n"
        "## Architettura\n"
        "Architettura solida.\n\n"
        "## Salute del codice\n"
        "Codice di alta qualita.\n"
    )

    report = ValidationReport(
        is_valid=False,
        quality_score=0.3,
        clarity_score=0.4,
        issues=[],
        actions=[
            "Rimuovere riferimento a Clean Architecture (non supportato dai dati)",
            "Sostituire giudizi morali con metriche concrete",
        ],
    )

    corrected = agent.correct(
        draft=draft,
        report=report,
        task=build_task(),
        skills=build_skills(),
    )

    # L'output dell'LLM viene ritornato non modificato
    assert "23 file Python" in corrected
    assert "Clean Architecture" not in corrected

    # Verifica che il prompt di correction
    # contenga draft e report
    assert len(agent.llm.prompts) == 1

    correction_prompt = agent.llm.prompts[0]

    # Il draft da correggere deve essere nel prompt
    assert (
        "Clean Architecture"
        in correction_prompt
    )

    # L'azione richiesta dal report deve essere nel prompt
    assert (
        "Rimuovere riferimento a Clean Architecture"
        in correction_prompt
    )

    # Marcatore unico di build_repo_correction_prompt
    assert (
        "OVERVIEW DA CORREGGERE"
        in correction_prompt
    )