from assist.core.project_context import ProjectContextBuilder
from assist.schemas.models import ProjectFileNode, ProjectGraph


def test_project_context_builds_summary():
    graph = ProjectGraph(
        root="project",
        files=[
            ProjectFileNode(
                path="project/main.py",
                module="main",
                imports=["utils"],
                imported_by=[],
                size_bytes=100,
                lines=10,
            ),
            ProjectFileNode(
                path="project/utils.py",
                module="utils",
                imports=[],
                imported_by=["main"],
                size_bytes=80,
                lines=8,
            ),
        ],
    )

    builder = ProjectContextBuilder()
    context = builder.build(graph)

    assert context.root == "project"
    assert context.total_files == 2
    assert "Repository contains 2 Python files" in context.summary
    assert len(context.primary_files) == 2