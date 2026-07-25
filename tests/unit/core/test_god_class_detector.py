from assist.core.god_class_detector import (
    GodClassDetector,
)

from assist.schemas.models import (
    ClassSymbol,
    FunctionSymbol,
)


def test_detect_god_class():

    methods = [
        FunctionSymbol(
            name=f"method_{i}",
            lineno=i,
            end_lineno=i + 1,
            line_count=2,
        )
        for i in range(12)
    ]

    class_symbol = ClassSymbol(
        name="MassiveManager",
        lineno=1,
        end_lineno=200,
        methods=methods,
    )

    result = (
        GodClassDetector()
        .analyze([class_symbol])
    )

    assert len(result.findings) == 1

    assert (
        result.findings[0]
        .class_name
        == "MassiveManager"
    )