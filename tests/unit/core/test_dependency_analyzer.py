from assist.core.dependency_analyzer import (
    DependencyAnalyzer,
)


def test_extract_imports(tmp_path):

    file = tmp_path / "app.py"

    file.write_text(
        """
import os
import sys

from pathlib import Path
from typing import Any
        """,
        encoding="utf-8",
    )

    imports = (
        DependencyAnalyzer.extract_imports(
            str(file)
        )
    )

    assert "os" in imports
    assert "sys" in imports
    assert "pathlib" in imports
    assert "typing" in imports