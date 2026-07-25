from assist.core.code_quality_analyzer import (
    CodeQualityAnalyzer,
)

from assist.schemas.models import (
    SemanticAnalysis,
    FunctionInfo,
    ProjectGraph,
)


def test_code_quality_report():

    semantic = SemanticAnalysis(
        functions=[
            FunctionInfo(
                name="huge_function",
                line_count=120,
            ),
        ],
        classes=[],
        imports=[],
        calls=[],
    )

    graph = ProjectGraph(
        root=".",
        files=[],
    )

    report = (
        CodeQualityAnalyzer()
        .analyze(
            semantic,
            graph,
        )
    )

    assert (
        "huge_function"
        in report.dead_functions
    )

    assert (
        "huge_function"
        in report.long_methods
    )