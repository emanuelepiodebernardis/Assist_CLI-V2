from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.orchestrator import (
    Orchestrator,
)
from assist.llm.factory import (
    LLMFactory,
)
from assist.schemas.models import (
    FinalOutput,
)


DRAFT_INCOMPLETE = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_add_happy_path():\n"
    "    assert add(1, 2) == 3\n"
)


SELF_CHECK_INVALID_JSON = (
    "{\n"
    '  "is_valid": false,\n'
    '  "quality_score": 0.55,\n'
    '  "clarity_score": 0.70,\n'
    '  "issues": [\n'
    "    {\n"
    '      "severity": "medium",\n'
    '      "message": "Missing edge case coverage.",\n'
    '      "location": "test_add_happy_path"\n'
    "    }\n"
    "  ],\n"
    '  "actions": [\n'
    '    "Add test for edge case with zero values"\n'
    "  ]\n"
    "}\n"
)


DRAFT_CORRECTED = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_add_happy_path():\n"
    "    assert add(1, 2) == 3\n"
    "\n"
    "\n"
    "def test_add_edge_case_zeros():\n"
    "    assert add(0, 0) == 0\n"
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

        self._responses = list(
            responses
        )

        self.prompts: list[str] = []

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:

        self.prompts.append(
            prompt
        )

        if not self._responses:
            raise AssertionError(
                "LLM called more times than expected. "
                f"Total prompts received: {len(self.prompts)}"
            )

        return self._responses.pop(0)


def test_test_flow_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    patch_all_analyzers,
):

    target_file = (
        tmp_path
        / "math_utils.py"
    )

    target_file.write_text(
        (
            "def add(a, b):\n"
            "    return a + b\n"
        ),
        encoding="utf-8",
    )

    llm = SequencedMockLLM(
        responses=[
            DRAFT_INCOMPLETE,
            SELF_CHECK_INVALID_JSON,
            DRAFT_CORRECTED,
            SELF_CHECK_VALID_JSON,
        ]
    )

    monkeypatch.setattr(
        LLMFactory,
        "create",
        lambda provider="anthropic": llm,
    )

    patch_all_analyzers(
        target_file,
        module_name="math_utils",
    )

    orchestrator = (
        Orchestrator()
    )

    task_model = (
        orchestrator.registry.task_model
        if hasattr(
            orchestrator.registry,
            "task_model",
        )
        else __import__(
            "assist.schemas.models",
            fromlist=["TaskInput"],
        ).TaskInput
    )

    result = orchestrator.run(
        task=task_model(
            command="test",
            file_path=str(
                target_file
            ),
            language="python",
            options={},
        )
    )

    # Tipo di ritorno
    assert isinstance(
        result,
        FinalOutput,
    )

    # Il contenuto finale deve riflettere il DRAFT_CORRECTED
    # (cioe' deve contenere il test che e' stato aggiunto
    # nel ciclo di correzione)
    assert (
        "def test_"
        in result.raw_content
    )

    assert (
        "assert add"
        in result.raw_content
    )

    # Marker della correzione: il test di edge case
    # esisteva solo nel DRAFT_CORRECTED, non nel DRAFT_INCOMPLETE
    assert (
        "test_add_edge_case_zeros"
        in result.raw_content
    )

    # Verifica del passaggio del verifier finale
    assert (
        result.verification.passed
        is True
    )

    assert (
        result.verification.syntax_ok
        is True
    )

    # Identita' del task e dell'agent
    assert (
        result.task_type
        == "test"
    )

    assert (
        result.agent_name
        == "TestGeneratorAgent"
    )

    # Il loop ha fatto esattamente 4 chiamate LLM:
    # draft1, self_check1 (fallisce), draft_corretto, self_check2 (passa)
    assert (
        len(llm.prompts)
        == 4
    )

    # Quality score del self_check FINALE (post-correzione)
    # confermata da BaseAgent loop ristrutturato
    assert (
        result.quality_score
        == pytest.approx(0.91)
    )

    # Iterations used: 2 = (draft iniziale + 1 correzione)
    assert (
        result.iterations_used
        == 2
    )