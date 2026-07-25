"""Shared fixtures for integration tests.

This module provides centralized monkeypatching of all analyzers used
by the Orchestrator in the file-path code path. Each integration test
that exercises a single-file task (review, generate, refactor, test)
uses the `patch_all_analyzers` factory fixture to mock out the static
analysis pipeline.

The diff integration test (test_diff_flow.py) does NOT use this fixture
because it exercises the git_range code path, which mocks the
GitDiffExtractor instead.

Usage in a test:

    def test_something(
        monkeypatch,
        tmp_path,
        patch_all_analyzers,
    ):
        sample_file = tmp_path / "sample.py"
        sample_file.write_text("...")

        patch_all_analyzers(
            sample_file,
            module_name="sample",
            semantic_calls=["print"],
        )

        # ... rest of test
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from assist.core.architectural_risk_analyzer import (
    ArchitecturalRiskAnalyzer,
)
from assist.core.architecture_analyzer import (
    ArchitectureAnalyzer,
)
from assist.core.code_quality_analyzer import (
    CodeQualityAnalyzer,
)
from assist.core.cross_file_analyzer import (
    CrossFileAnalyzer,
)
from assist.core.project_graph import (
    ProjectGraphBuilder,
)
from assist.core.project_scanner import (
    ProjectScanner,
)
from assist.core.repository_context import (
    RepositoryContextBuilder,
)
from assist.core.repository_health import (
    RepositoryHealthAnalyzer,
)
from assist.core.semantic_analyzer import (
    SemanticAnalyzer,
)
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
)


@pytest.fixture
def patch_all_analyzers(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    """Factory fixture to patch all analyzers.

    Returns a callable that, when invoked with a sample_file path
    (and optional overrides), monkeypatches all 9 analyzers used
    by the Orchestrator in the file-path branch.

    The returned callable does not require monkeypatch as argument
    because it is captured from the enclosing fixture scope.
    """

    def _patch(
        sample_file: Path,
        *,
        module_name: str = "sample",
        function_name: str = "add",
        function_line_count: int = 2,
        function_complexity: int = 1,
        function_lineno: int = 1,
        function_end_lineno: int = 2,
        semantic_calls: list[str] | None = None,
        health_score: float = 1.0,
        related_files: list[str] | None = None,
    ) -> None:

        if semantic_calls is None:
            semantic_calls = []

        if related_files is None:
            related_files = []

        file_node = ProjectFileNode(
            path=str(sample_file),
            module=module_name,
            imports=[],
            imported_by=[],
            size_bytes=sample_file.stat().st_size,
            lines=len(
                sample_file
                .read_text(encoding="utf-8")
                .splitlines()
            ),
        )

        monkeypatch.setattr(
            ProjectScanner,
            "scan",
            lambda self, root: [
                FileMetadata(
                    path=str(sample_file),
                    size_bytes=sample_file.stat().st_size,
                    lines=file_node.lines,
                )
            ],
        )

        monkeypatch.setattr(
            RepositoryContextBuilder,
            "build",
            lambda self,
            target_file,
            project_files: {
                "related_files": related_files,
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
                    health_score=health_score,
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
                        name=function_name,
                        line_count=function_line_count,
                        complexity=function_complexity,
                        lineno=function_lineno,
                        end_lineno=function_end_lineno,
                    )
                ],
                classes=[],
                imports=[],
                calls=semantic_calls,
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
            lambda self, semantic, graph, tree=None: (
                CodeQualityReport(
                    complexity_warnings=[],
                    dead_functions=[],
                    architectural_risks=[],
                    long_methods=[],
                    god_classes=[],
                )
            ),
        )

    return _patch