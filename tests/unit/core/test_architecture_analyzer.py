from assist.core.architecture_analyzer import ArchitectureAnalyzer
from assist.schemas.models import ProjectFileNode, ProjectGraph


def test_detects_cyclic_dependency():
    graph = ProjectGraph(
        root="project",
        files=[
            ProjectFileNode(
                path="project/a.py",
                module="a",
                imports=["b"],
                imported_by=["b"],
                size_bytes=100,
                lines=10,
            ),
            ProjectFileNode(
                path="project/b.py",
                module="b",
                imports=["a"],
                imported_by=["a"],
                size_bytes=90,
                lines=8,
            ),
        ],
    )

    report = ArchitectureAnalyzer().detect_cycles(graph)

    assert report.has_cycles is True
    assert ["a", "b", "a"] in report.cycles
    assert len(report.issues) == 1