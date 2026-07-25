from assist.core.dependency_graph import (
    DependencyGraph,
)

from assist.schemas.models import (
    FileMetadata,
)


def test_build_dependency_graph(tmp_path):

    app = tmp_path / "app.py"

    app.write_text(
        """
import os
from pathlib import Path
        """,
        encoding="utf-8",
    )

    metadata = FileMetadata(
        path=str(app),
        size_bytes=100,
        lines=2,
    )

    graph = DependencyGraph().build(
        [metadata]
    )

    assert str(app) in graph

    imports = graph[str(app)]

    assert "os" in imports
    assert "pathlib" in imports