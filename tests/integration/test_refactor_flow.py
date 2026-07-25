from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.orchestrator import Orchestrator
from assist.llm.factory import LLMFactory
from assist.schemas.models import (
    TaskInput,
)


# Le triple-quote interne ai response devono usare delimitatori sicuri.
# Per evitare ogni conflitto con i ``` markdown, costruiamo le stringhe
# pezzo per pezzo invece di usare triple-quote annidate.

DRAFT_INVALID = (
    "## Modifiche apportate\n\n"
    "- Aggiunti type hints.\n\n"
    "## Codice refactorizzato\n\n"
    "```python\n"
    "def add(a: int, b: int) -> int\n"
    "    return a + b\n"
    "```\n"
)


SELF_CHECK_INVALID_JSON = (
    "{\n"
    '  "is_valid": false,\n'
    '  "quality_score": 0.42,\n'
    '  "clarity_score": 0.50,\n'
    '  "issues": [\n'
    "    {\n"
    '      "severity": "high",\n'
    '      "message": "Missing colon in function signature.",\n'
    '      "location": null\n'
    "    }\n"
    "  ],\n"
    '  "actions": [\n'
    '    "Fix the function signature syntax."\n'
    "  ]\n"
    "}\n"
)


DRAFT_CORRECTED = (
    "## Modifiche apportate\n\n"
    "- Aggiunti type hints.\n"
    "- Corretto errore di sintassi nella signature.\n\n"
    "## Codice refactorizzato\n\n"
    "```python\n"
    "def add(a: int, b: int) -> int:\n"
    "    return a + b\n"
    "\n\n"
    'if __name__ == "__main__":\n'
    "    print(add(1, 2))\n"
    "```\n"
)


SELF_CHECK_VALID_JSON = (
    "{\n"
    '  "is_valid": true,\n'
    '  "quality_score": 0.91,\n'
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


def test_refactor_flow_converges_after_correction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    patch_all_analyzers,
) -> None:

    sample_file = tmp_path / "bad_module.py"

    sample_file.write_text(
        "def add(a,b):\n"
        "    return a+b\n"
        "\n"
        "print(add(1,2))\n",
        encoding="utf-8",
    )

    llm = SequencedMockLLM(
        responses=[
            DRAFT_INVALID,
            SELF_CHECK_INVALID_JSON,
            DRAFT_CORRECTED,
            SELF_CHECK_VALID_JSON,
        ],
    )

    monkeypatch.setattr(
        LLMFactory,
        "create",
        lambda provider="anthropic": llm,
    )

    patch_all_analyzers(
        sample_file,
        module_name="bad_module",
        semantic_calls=["print"],
        related_files=[str(sample_file)],
        health_score=0.93,
    )

    orchestrator = Orchestrator()

    result = orchestrator.run(
        task=TaskInput(
            command="refactor",
            file_path=str(sample_file),
        )
    )

    assert "def add(a: int, b: int)" in result.raw_content

    assert "__main__" in result.raw_content

    assert result.verification.syntax_ok is True

    assert result.verification.passed is True

    assert result.iterations_used == 2

    assert len(llm.prompts) == 4

    assert (
        "CONTESTO STRUTTURALE DEL PROGETTO"
        in llm.prompts[0]
    )

    assert (
        "REFACTORING PROPOSTO DA VALIDARE"
        in llm.prompts[1]
    )

    assert (
        "REFACTORING DA CORREGGERE"
        in llm.prompts[2]
    )

    assert (
        "REFACTORING PROPOSTO DA VALIDARE"
        in llm.prompts[3]
    )