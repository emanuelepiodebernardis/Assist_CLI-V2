from assist.core.long_method_detector import (
    LongMethodDetector,
)

from assist.schemas.models import (
    FunctionSymbol,
    SemanticFileAnalysis,
)


def test_detect_long_method():

    function = FunctionSymbol(
        name="massive_function",
        lineno=1,
        end_lineno=120,
        line_count=120,
    )

    semantic = SemanticFileAnalysis(
        path="test.py",
        functions=[function],
        classes=[],
        imports=[],
        calls=[],
    )

    result = (
        LongMethodDetector()
        .analyze(semantic)
    )

    assert len(result.findings) == 1

    assert (
        result.findings[0]
        .function_name
        == "massive_function"
    )