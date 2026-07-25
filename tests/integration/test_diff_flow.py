from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.git_diff_extractor import (
    GitDiffExtractor,
)
from assist.core.orchestrator import (
    Orchestrator,
)
from assist.llm.factory import (
    LLMFactory,
)
from assist.schemas.models import (
    FileDiff,
    FinalOutput,
    GitDiff,
    TaskInput,
)


# =====================================================================
# Payload mock LLM
#
# Il flusso del task "diff" passa per il loop standard di BaseAgent:
#   draft -> self_check -> (eventualmente correct -> self_check finale)
#
# DiffReviewerAgent ha MAX_CORRECTIONS = 1, quindi il loop totale e':
#   1. draft iniziale
#   2. self_check #1 (se fallisce, correzione)
#   3. correzione (al massimo 1)
#   4. self_check #2 (finale)
#
# In questo test simuliamo: draft incompleto -> self_check fallisce ->
# correct -> self_check passa. Quattro chiamate LLM totali.
# =====================================================================


DRAFT_INCOMPLETE = (
    "## Sommario\n"
    "Il diff modifica foo.\n"
    "\n"
    "## Modifiche rilevanti\n"
    "- module.py: cambio valore ritorno.\n"
)


SELF_CHECK_INVALID_JSON = (
    "{\n"
    '  "is_valid": false,\n'
    '  "quality_score": 0.55,\n'
    '  "clarity_score": 0.70,\n'
    '  "issues": [\n'
    "    {\n"
    '      "severity": "medium",\n'
    '      "message": "Missing risks section for breaking change.",\n'
    '      "location": "module.py"\n'
    "    }\n"
    "  ],\n"
    '  "actions": [\n'
    '    "Add risks section about callers"\n'
    "  ]\n"
    "}\n"
)


DRAFT_CORRECTED = (
    "## Sommario\n"
    "Il diff modifica foo da 1 a 2.\n"
    "\n"
    "## Modifiche rilevanti\n"
    "- module.py:2: foo() ritorna 2 invece di 1.\n"
    "\n"
    "## Rischi\n"
    "- module.py:2 (medium): chiamanti di foo che si "
    "aspettano il valore 1 potrebbero non funzionare "
    "correttamente dopo questa modifica.\n"
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


# =====================================================================
# Mock del diff: invece di un repo git reale, simuliamo
# l'output del GitDiffExtractor con un GitDiff costruito a mano.
# =====================================================================


MOCK_RAW_DIFF = (
    "diff --git a/module.py b/module.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/module.py\n"
    "+++ b/module.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def foo():\n"
    "-    return 1\n"
    "+    return 2\n"
)


MOCK_FILE_DIFF = FileDiff(
    path="module.py",
    additions=1,
    deletions=1,
    hunks=MOCK_RAW_DIFF,
)


MOCK_GIT_DIFF = GitDiff(
    range_spec="HEAD",
    files=[MOCK_FILE_DIFF],
    files_changed=1,
    total_additions=1,
    total_deletions=1,
    raw_diff=MOCK_RAW_DIFF,
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


# =====================================================================
# Test
# =====================================================================


def test_diff_flow_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):

    # Setup: crea il file "impattato" su disco
    # (l'orchestrator legge il contenuto dei file
    # modificati dal disco)
    impacted_file = tmp_path / "module.py"

    impacted_file.write_text(
        (
            "def foo():\n"
            "    return 2\n"
        ),
        encoding="utf-8",
    )

    # Mock del GitDiffExtractor.extract:
    # restituisce sempre il MOCK_GIT_DIFF ma con
    # path aggiornato al tmp_path in modo che
    # file_path_obj.read_text() trovi il file
    mock_file_diff = FileDiff(
        path=str(impacted_file),
        additions=1,
        deletions=1,
        hunks=MOCK_RAW_DIFF,
    )

    mock_git_diff = GitDiff(
        range_spec="HEAD",
        files=[mock_file_diff],
        files_changed=1,
        total_additions=1,
        total_deletions=1,
        raw_diff=MOCK_RAW_DIFF,
    )

    monkeypatch.setattr(
        GitDiffExtractor,
        "extract",
        lambda self, range_spec: mock_git_diff,
    )

    # Setup del mock LLM con le 4 risposte attese
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

    # Esegui il task diff
    orchestrator = Orchestrator()

    result = orchestrator.run(
        task=TaskInput(
            command="diff",
            git_range="HEAD",
            options={},
        )
    )

    # =================================================================
    # Verifiche del risultato finale
    # =================================================================

    # Tipo di ritorno
    assert isinstance(
        result,
        FinalOutput,
    )

    # Il contenuto finale deve riflettere il DRAFT_CORRECTED:
    # contiene le tre sezioni
    # (Sommario, Modifiche rilevanti, Rischi)
    assert (
        "## Sommario"
        in result.raw_content
    )

    assert (
        "## Modifiche rilevanti"
        in result.raw_content
    )

    # Marker del ciclo di correzione:
    # la sezione "## Rischi"
    # esisteva solo nel DRAFT_CORRECTED,
    # non nel DRAFT_INCOMPLETE
    assert (
        "## Rischi"
        in result.raw_content
    )

    # Identita' del task e dell'agent
    assert (
        result.task_type
        == "diff"
    )

    assert (
        result.agent_name
        == "DiffReviewerAgent"
    )

    # Il loop ha fatto 4 chiamate LLM:
    # draft1, self_check1 (fallisce),
    # correzione, self_check2 (passa)
    assert (
        len(llm.prompts)
        == 4
    )

    # Quality score del self_check FINALE
    # (post-correzione)
    assert (
        result.quality_score
        == pytest.approx(0.91)
    )

    # Iterations = 2
    # (draft iniziale + 1 correzione)
    assert (
        result.iterations_used
        == 2
    )

    # =================================================================
    # Verifiche del prompt iniziale
    # (controllo che il diff sia stato
    # correttamente iniettato dall'orchestrator)
    # =================================================================

    initial_prompt = llm.prompts[0]

    # Il prompt deve contenere il diff git testuale.
    # Marker tipico del diff: header diff --git
    assert (
        "diff --git a/module.py b/module.py"
        in initial_prompt
    )

    # Il prompt deve contenere il contenuto
    # del file impattato
    # (popolato dall'orchestrator
    # leggendolo dal disco)
    assert (
        "def foo():"
        in initial_prompt
    )

    # Il prompt deve contenere il range git
    assert (
        "HEAD"
        in initial_prompt
    )

    # Marcatore unico di build_diff_prompt
    assert (
        "ESEGUI ORA LA REVIEW DEL DIFF"
        in initial_prompt
    )