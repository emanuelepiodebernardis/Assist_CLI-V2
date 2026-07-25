import ast

from assist.core.complexity_analyzer import (
    ComplexityAnalyzer,
)

from assist.core.semantic_analyzer import (
    SemanticAnalyzer,
)


def test_detect_function_complexity(tmp_path):
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        """
def simple(x):
    return x


def complex_function(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                x -= i
    return x
        """,
        encoding="utf-8",
    )

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    semantic = SemanticAnalyzer().analyze_file(
        str(file_path)
    )

    result = ComplexityAnalyzer().analyze(
        tree,
        semantic,
    )

    simple_fn = next(
        fn for fn in result.functions
        if fn.name == "simple"
    )

    complex_fn = next(
        fn for fn in result.functions
        if fn.name == "complex_function"
    )

    assert simple_fn.complexity == 1
    assert complex_fn.complexity > 1