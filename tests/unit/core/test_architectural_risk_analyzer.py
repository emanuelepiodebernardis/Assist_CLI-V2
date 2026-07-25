from assist.core.architectural_risk_analyzer import (
    ArchitecturalRiskAnalyzer,
)

from assist.schemas.models import (
    ProjectFileNode,
    ProjectGraph,
)


def test_detect_high_coupling():

    node = ProjectFileNode(
        path="core.py",
        module="core",
        imports=[
            f"module_{i}.py"
            for i in range(12)
        ],
        imported_by=[],
        size_bytes=100,
        lines=20,
    )

    graph = ProjectGraph(
        root=".",
        files=[node],
    )

    result = (
        ArchitecturalRiskAnalyzer()
        .analyze(graph)
    )

    assert len(result.risks) > 0

    assert (
        result.risks[0].risk_type
        == "high_coupling"
    )