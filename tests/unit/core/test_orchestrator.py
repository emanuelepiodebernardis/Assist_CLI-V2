from __future__ import annotations

from pathlib import Path

import pytest

from assist.core.architecture_analyzer import ArchitectureAnalyzer
from assist.core.architectural_risk_analyzer import (
    ArchitecturalRiskAnalyzer,
)
from assist.core.code_quality_analyzer import CodeQualityAnalyzer
from assist.core.cross_file_analyzer import CrossFileAnalyzer
from assist.core.orchestrator import Orchestrator
from assist.core.project_graph import ProjectGraphBuilder
from assist.core.project_scanner import ProjectScanner
from assist.core.repository_context import RepositoryContextBuilder
from assist.core.repository_health import RepositoryHealthAnalyzer
from assist.core.semantic_analyzer import SemanticAnalyzer
from assist.llm.factory import LLMFactory
from assist.schemas.models import (
    ArchitecturalRiskReport,
    ArchitectureReport,
    CodeQualityReport,
    CrossFileAnalysis,
    FileMetadata,
    FunctionInfo,
    ProjectFileNode,
    ProjectGraph,
    RepositoryHealthReport,
    SemanticAnalysis,
    TaskInput,
)


REVIEW_DRAFT = (
    "## Sommario\n\n"
    "Il file presenta problemi minori di stile.\n\n"
    "## Problemi critici\n\n"
    "Nessuno.\n\n"
    "## Problemi significativi\n\n"
    "Nessuno.\n"
)


SELF_CHECK_VALID_JSON = (
    "{\n"
    '  "is_valid": true,\n'
    '  "quality_score": 0.87,\n'
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


def test_orchestrator_runs_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:

    sample_file = tmp_path / "test.py"

    sample_file.write_text(
        "def hello() -> str:\n"
        '    return "world"\n',
        encoding="utf-8",
    )

    llm = SequencedMockLLM(
        responses=[
            REVIEW_DRAFT,
            SELF_CHECK_VALID_JSON,
        ]
    )

    monkeypatch.setattr(
        LLMFactory,
        "create",
        lambda provider="anthropic": llm,
    )

    file_node = ProjectFileNode(
        path=str(sample_file),
        module="test",
        imports=[],
        imported_by=[],
        size_bytes=sample_file.stat().st_size,
        lines=2,
    )

    monkeypatch.setattr(
        ProjectScanner,
        "scan",
        lambda self, root: [file_node],
    )

    monkeypatch.setattr(
        RepositoryContextBuilder,
        "build",
        lambda self, target_file, project_files: {
            "related_files": [],
            "project_size": len(project_files),
        },
    )

    monkeypatch.setattr(
        ProjectGraphBuilder,
        "build",
        lambda self, root: ProjectGraph(
            root=str(root),
            files=[file_node],
        ),
    )

    monkeypatch.setattr(
        ArchitectureAnalyzer,
        "detect_cycles",
        lambda self, graph: ArchitectureReport(
            has_cycles=False,
            cycles=[],
            issues=[],
        ),
    )

    monkeypatch.setattr(
        RepositoryHealthAnalyzer,
        "analyze",
        lambda self, graph, cycles: (
            RepositoryHealthReport(
                total_files=len(graph.files),
                total_dependencies=0,
                cyclic_dependencies=len(cycles),
                highly_connected_files=[],
                health_score=0.95,
                issues=[],
            )
        ),
    )

    monkeypatch.setattr(
        ArchitecturalRiskAnalyzer,
        "analyze",
        lambda self, graph: (
            ArchitecturalRiskReport(risks=[])
        ),
    )

    monkeypatch.setattr(
        SemanticAnalyzer,
        "analyze_file",
        lambda self, file_path: SemanticAnalysis(
            path=str(file_path),
            functions=[
                FunctionInfo(
                    name="hello",
                    line_count=2,
                    complexity=1,
                    lineno=1,
                    end_lineno=2,
                )
            ],
            classes=[],
            imports=[],
            calls=[],
        ),
    )

    monkeypatch.setattr(
        CrossFileAnalyzer,
        "analyze",
        lambda self, project_files: (
            CrossFileAnalysis(
                imports=[],
                function_calls=[],
            )
        ),
    )

    monkeypatch.setattr(
        CodeQualityAnalyzer,
        "analyze",
        lambda self, semantic, graph, tree: (
            CodeQualityReport(
                complexity_warnings=[],
                dead_functions=[],
                architectural_risks=[],
                long_methods=[],
                god_classes=[],
            )
        ),
    )

    orchestrator = Orchestrator()

    task = TaskInput(
        command="review",
        file_path=str(sample_file),
    )

    result = orchestrator.run(task)

    assert result.task_type == "review"

    assert result.agent_name == "ReviewerAgent"

    assert "## Sommario" in result.raw_content

    assert isinstance(
        result.quality_score,
        float,
    )