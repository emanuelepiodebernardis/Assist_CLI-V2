from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.architecture_analyzer import (
    ArchitectureAnalyzer,
)
from assist.core.architectural_risk_analyzer import (
    ArchitecturalRiskAnalyzer,
)
from assist.core.code_quality_analyzer import (
    CodeQualityAnalyzer,
)
from assist.core.cross_file_analyzer import (
    CrossFileAnalyzer,
)
from assist.core.orchestrator import (
    Orchestrator,
)
from assist.core.project_graph import (
    ProjectGraphBuilder,
)
from assist.core.project_scanner import (
    ProjectScanner,
)
from assist.core.repository_health import (
    RepositoryHealthAnalyzer,
)
from assist.core.semantic_analyzer import (
    SemanticAnalyzer,
)
from assist.llm.factory import (
    LLMFactory,
)
from assist.schemas.models import (
    ArchitectureReport,
    ArchitecturalRiskReport,
    CodeQualityReport,
    CrossFileAnalysis,
    FinalOutput,
    ProjectGraph,
    RepositoryHealthReport,
    SemanticAnalysis,
    TaskInput,
)


# =====================================================================
# Payload mock LLM
#
# Per il task "repo", testiamo il caso happy path:
# il draft iniziale passa il self_check al primo tentativo.
# Due chiamate LLM totali: draft + self_check valido.
#
# La logica del loop di correzione e' gia' coperta dai test
# unit di RepoAgent (test_correct_returns_fixed_overview).
# Qui ci concentriamo sul wire-up end-to-end.
# =====================================================================


DRAFT_OVERVIEW = (
    "## Panoramica\n"
    "Il repository contiene 0 file Python (mock vuoto). "
    "Path analizzato: tmp_path.\n"
    "\n"
    "## Architettura\n"
    "Nessun ciclo di import rilevato. "
    "Health score: 1.0 (nessuna metrica negativa).\n"
    "\n"
    "## Salute del codice\n"
    "Nessuna god class, nessun long method, "
    "nessun complexity warning rilevato. "
    "Codebase di dimensioni minime nel mock di test.\n"
)


SELF_CHECK_VALID_JSON = (
    "{\n"
    '  "is_valid": true,\n'
    '  "quality_score": 0.88,\n'
    '  "clarity_score": 0.85,\n'
    '  "issues": [],\n'
    '  "actions": []\n'
    "}\n"
)


# =====================================================================
# Mock reports vuoti per gli analyzer.
# Restituiscono strutture valide ma con dati minimi,
# in modo che il context aggregato sia popolato
# senza richiedere un vero progetto sul disco.
# =====================================================================


MOCK_PROJECT_GRAPH = ProjectGraph(
    root="tmp_path",
    files=[],
)


MOCK_ARCHITECTURE_REPORT = ArchitectureReport(
    has_cycles=False,
    cycles=[],
    issues=[],
)


MOCK_HEALTH_REPORT = RepositoryHealthReport(
    total_files=0,
    total_dependencies=0,
    cyclic_dependencies=0,
    highly_connected_files=[],
    health_score=1.0,
    issues=[],
)


MOCK_RISK_REPORT = ArchitecturalRiskReport(
    risks=[],
)


MOCK_CROSS_FILE_ANALYSIS = CrossFileAnalysis(
    imports=[],
    function_calls=[],
)


MOCK_SEMANTIC_ANALYSIS = SemanticAnalysis(
    path="",
    functions=[],
    classes=[],
    imports=[],
    calls=[],
)


MOCK_CODE_QUALITY_REPORT = CodeQualityReport(
    complexity_warnings=[],
    dead_functions=[],
    architectural_risks=[],
    long_methods=[],
    god_classes=[],
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


def test_repo_flow_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):

    # Setup: crea un mini-repository fittizio con 1 file Python
    # nel tmp_path. Anche se gli analyzer sono mockati, il
    # ProjectScanner viene mockato per restituire una lista
    # vuota, quindi il file non viene letto. Il tmp_path serve
    # solo come argomento valido per validate_directory_exists
    # (passato via orchestrator -> validate del comando in CLI).
    # In questo test invochiamo Orchestrator direttamente, quindi
    # validate_directory_exists viene saltato.
    sample_file = tmp_path / "sample.py"

    sample_file.write_text(
        (
            "def hello():\n"
            "    return 'world'\n"
        ),
        encoding="utf-8",
    )

    # Mock di tutti gli analyzer del branch repo_path.
    # Ogni analyzer restituisce un report vuoto/valido,
    # in modo che il context aggregato sia popolato
    # ma senza richiedere logica reale.

    # ProjectScanner: restituisce lista vuota per evitare
    # iterazione sui file (e quindi chiamate a FileReader
    # e SemanticAnalyzer su file potenzialmente non parsabili)
    monkeypatch.setattr(
        ProjectScanner,
        "scan",
        lambda self, root: [],
    )

    monkeypatch.setattr(
        ProjectGraphBuilder,
        "build",
        lambda self, root: MOCK_PROJECT_GRAPH,
    )

    monkeypatch.setattr(
        ArchitectureAnalyzer,
        "detect_cycles",
        lambda self, graph: MOCK_ARCHITECTURE_REPORT,
    )

    monkeypatch.setattr(
        RepositoryHealthAnalyzer,
        "analyze",
        lambda self, graph, cycles: MOCK_HEALTH_REPORT,
    )

    monkeypatch.setattr(
        ArchitecturalRiskAnalyzer,
        "analyze",
        lambda self, graph: MOCK_RISK_REPORT,
    )

    monkeypatch.setattr(
        CrossFileAnalyzer,
        "analyze",
        lambda self, project_files: MOCK_CROSS_FILE_ANALYSIS,
    )

    monkeypatch.setattr(
        SemanticAnalyzer,
        "analyze_file",
        lambda self, path: MOCK_SEMANTIC_ANALYSIS,
    )

    monkeypatch.setattr(
        CodeQualityAnalyzer,
        "analyze",
        lambda self, semantic, graph, tree: MOCK_CODE_QUALITY_REPORT,
    )

    # Setup del mock LLM con le 2 risposte attese
    # (happy path: draft + self_check passa al primo tentativo)
    llm = SequencedMockLLM(
        responses=[
            DRAFT_OVERVIEW,
            SELF_CHECK_VALID_JSON,
        ]
    )

    monkeypatch.setattr(
        LLMFactory,
        "create",
        lambda provider="anthropic": llm,
    )

    # Esegui il task repo
    orchestrator = Orchestrator()

    result = orchestrator.run(
        task=TaskInput(
            command="repo",
            repo_path=str(tmp_path),
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

    # Il contenuto finale deve contenere le 3 sezioni
    # obbligatorie dell'overview
    assert (
        "## Panoramica"
        in result.raw_content
    )

    assert (
        "## Architettura"
        in result.raw_content
    )

    assert (
        "## Salute del codice"
        in result.raw_content
    )

    # Identita' del task e dell'agent
    assert (
        result.task_type
        == "repo"
    )

    assert (
        result.agent_name
        == "RepoAgent"
    )

    # Il loop ha fatto 2 chiamate LLM:
    # draft + self_check (valido al primo tentativo)
    assert (
        len(llm.prompts)
        == 2
    )

    # Quality score del self_check
    assert (
        result.quality_score
        == pytest.approx(0.88)
    )

    # Iterations = 1 (happy path, nessuna correzione)
    assert (
        result.iterations_used
        == 1
    )

    # =================================================================
    # Verifiche del prompt iniziale
    # (controllo che il context sia stato
    # correttamente iniettato dall'orchestrator)
    # =================================================================

    initial_prompt = llm.prompts[0]

    # Il prompt deve contenere il repo_path passato
    # come argomento del task
    assert (
        f"Path: {str(tmp_path)}"
        in initial_prompt
    )

    # Marcatore unico di build_repo_prompt
    assert (
        "ESEGUI ORA L'OVERVIEW"
        in initial_prompt
    )

    # Il prompt deve contenere i vincoli identitari
    # della skill repository_overview
    assert (
        "ANCORAGGIO AI DATI"
        in initial_prompt
    )

    assert (
        "NO INVENZIONE DI PATTERN"
        in initial_prompt
    )

    # =================================================================
    # Verifiche del prompt di self_check
    # =================================================================

    self_check_prompt = llm.prompts[1]

    # Il prompt di self_check deve contenere il draft
    # da validare
    assert (
        "Il repository contiene 0 file Python"
        in self_check_prompt
    )

    # Marcatore unico di build_repo_self_check_prompt
    assert (
        "OVERVIEW DA VALIDARE"
        in self_check_prompt
    )