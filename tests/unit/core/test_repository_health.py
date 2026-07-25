from assist.core.repository_health import (
    RepositoryHealthAnalyzer,
)

from assist.schemas.models import (
    ProjectFileNode,
    ProjectGraph,
)


def test_repository_health_analysis():

    graph = ProjectGraph(
        root="project",
        files=[
            ProjectFileNode(
                path="a.py",
                module="a",
                imports=[
                    "b",
                    "c",
                    "d",
                    "e",
                    "f",
                    "g",
                ],
                imported_by=[],
                size_bytes=100,
                lines=20,
            ),
            ProjectFileNode(
                path="b.py",
                module="b",
                imports=[],
                imported_by=["a"],
                size_bytes=80,
                lines=10,
            ),
        ],
    )

    analyzer = (
        RepositoryHealthAnalyzer()
    )

    report = analyzer.analyze(
        graph=graph,
        cycles=[["a", "b", "a"]],
    )

    assert report.total_files == 2

    assert (
        report.total_dependencies == 6
    )

    assert (
        report.cyclic_dependencies == 1
    )

    assert "a" in (
        report.highly_connected_files
    )

    assert report.health_score < 1.0