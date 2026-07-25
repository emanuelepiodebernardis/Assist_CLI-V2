from assist.core.semantic_analyzer import SemanticAnalyzer


def test_semantic_analyzer_extracts_symbols(tmp_path):
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        """
import os
from pathlib import Path

def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y

print(add(1, 2))
        """,
        encoding="utf-8",
    )

    analysis = SemanticAnalyzer().analyze_file(str(file_path))

    assert "os" in analysis.imports
    assert "pathlib" in analysis.imports
    assert any(f.name == "add" for f in analysis.functions)
    assert any(c.name == "Calculator" for c in analysis.classes)
    assert "print" in analysis.calls