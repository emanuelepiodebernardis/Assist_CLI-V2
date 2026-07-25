from assist.core.dead_code_detector import (
    DeadCodeDetector,
)

from assist.schemas.models import (
    FunctionSymbol,
)


def test_detect_unused_functions():

    functions = [
        FunctionSymbol(
            name="used_function",
            lineno=1,
            end_lineno=5,
            line_count=5,
        ),
        FunctionSymbol(
            name="unused_function",
            lineno=10,
            end_lineno=20,
            line_count=10,
        ),
    ]

    calls = [
        "used_function",
    ]

    unused = (
        DeadCodeDetector()
        .detect_unused_functions(
            functions,
            calls,
        )
    )

    assert (
        "unused_function"
        in unused
    )

    assert (
        "used_function"
        not in unused
    )