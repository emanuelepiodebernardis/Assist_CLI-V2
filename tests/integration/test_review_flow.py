from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.orchestrator import Orchestrator
from assist.llm.factory import LLMFactory


REVIEW_DRAFT_GENERIC = (
    "## Sommario\n\n"
    "Il file contiene problemi di stile "
    "e una credenziale hardcoded.\n"
)


SELF_CHECK_INVALID_JSON = (
    "{\n"
    '  "is_valid": false,\n'
    '  "quality_score": 0.45,\n'
    '  "clarity_score": 0.60,\n'
    '  "issues": [\n'
    "    {\n"
    '      "severity": "medium",\n'
    '      "message": "La review e troppo generica.",\n'
    '      "location": null\n'
    "    }\n"
    "  ],\n"
    '  "actions": [\n'
    '    "Aggiungere dettagli specifici sui problemi.",\n'
    '    "Migliorare la sezione dei fix."\n'
    "  ]\n"
    "}\n"
)


REVIEW_DRAFT_CORRECTED = (
    "## Sommario\n\n"
    "Il file `sample.py` contiene una funzione semplice ma presenta "
    "problemi di stile e una credenziale hardcoded.\n\n"
    "## Problemi critici\n"
    '- `password = "12345"` espone una credenziale in chiaro.\n\n'
    "## Problemi significativi\n"
    "- L'indentazione e incoerente.\n"
    "- Mancano type hints.\n"
    "- La chiamata `print(add(1,2))` non e formattata secondo PEP 8.\n\n"
    "## Suggerimenti\n"
    "- Usare `APP_PASSWORD` da variabili d'ambiente.\n"
    "- Aggiungere type hints e docstring.\n"
    "- Correggere spaziatura e indentazione.\n"
)


SELF_CHECK_VALID_JSON = (
    "{\n"
    '  "is_valid": true,\n'
    '  "quality_score": 0.88,\n'
    '  "clarity_score": 0.90,\n'
    '  "issues": [],\n'
    '  "actions": []\n'
    "}\n"
)


class SequencedMockLLM:

    def __init__(
        self,
        responses: list[str],
    ) -> None:

        self._responses = list(responses)

        self.prompts: list[str] = []

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:

        self.prompts.append(prompt)

        if not self._responses:
            raise AssertionError(
                "LLM called more times than expected. "
                f"Total prompts received: {len(self.prompts)}"
            )

        return self._responses.pop(0)


def test_review_flow_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    patch_all_analyzers,
):

    sample_file = tmp_path / "sample.py"

    sample_file.write_text(
        'def add(a, b):\n'
        ' return a+b\n'
        '\n'
        'password = "12345"\n'
        '\n'
        'print(add(1,2))\n',
        encoding="utf-8",
    )

    llm = SequencedMockLLM(
        responses=[
            REVIEW_DRAFT_GENERIC,
            SELF_CHECK_INVALID_JSON,
            REVIEW_DRAFT_CORRECTED,
            SELF_CHECK_VALID_JSON,
        ]
    )

    monkeypatch.setattr(
        LLMFactory,
        "create",
        lambda provider="anthropic": llm,
    )

    patch_all_analyzers(
        sample_file,
        module_name="sample",
        semantic_calls=["print"],
        related_files=[str(sample_file)],
        health_score=0.92,
    )

    orchestrator = Orchestrator()

    result = orchestrator.run(
        task=(
            orchestrator.registry.task_model(
                command="review",
                file_path=str(sample_file),
            )
            if hasattr(
                orchestrator.registry,
                "task_model",
            )
            else __import__(
                "assist.schemas.models",
                fromlist=["TaskInput"],
            ).TaskInput(
                command="review",
                file_path=str(sample_file),
            )
        )
    )

    assert result.task_type == "review"

    assert result.agent_name == "ReviewerAgent"

    assert "## Sommario" in result.raw_content

    assert (
        "Problemi critici"
        in result.raw_content
    )

    assert len(llm.prompts) == 4

    assert (
        "CONTESTO STRUTTURALE DEL PROGETTO"
        in llm.prompts[0]
    )

    assert (
        'password = "12345"'
        in llm.prompts[0]
    )

    assert isinstance(
        result.quality_score,
        float,
    )

    assert result.quality_score == pytest.approx(0.88)