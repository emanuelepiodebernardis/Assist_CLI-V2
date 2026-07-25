from assist.core.repository_context import (
    RepositoryContextBuilder,
)

from assist.schemas.models import (
    FileMetadata,
)


def test_build_repository_context(tmp_path):

    app = tmp_path / "app.py"

    app.write_text(
        """
import os
import assist.core.registry
        """,
        encoding="utf-8",
    )

    project_files = [
        FileMetadata(
            path=str(app),
            size_bytes=100,
            lines=2,
        ),
        FileMetadata(
            path="assist/core/registry.py",
            size_bytes=200,
            lines=10,
        ),
    ]

    context = (
        RepositoryContextBuilder().build(
            str(app),
            project_files,
        )
    )

    assert "os" in context["imports"]

    assert (
        "assist.core.registry"
        in context[
            "internal_dependencies"
        ]
    )

    assert context["project_size"] == 2