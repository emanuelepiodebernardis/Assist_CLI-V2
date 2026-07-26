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


def test_dunder_method_is_not_flagged():
    functions = [
        FunctionSymbol(
            name="__init__",
            lineno=1,
            end_lineno=3,
            line_count=3,
        ),
        FunctionSymbol(
            name="__str__",
            lineno=5,
            end_lineno=7,
            line_count=3,
        ),
    ]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls=[],
    )

    assert "__init__" not in unused
    assert "__str__" not in unused


def test_test_prefixed_function_is_not_flagged():
    functions = [
        FunctionSymbol(
            name="test_something_works",
            lineno=1,
            end_lineno=3,
            line_count=3,
        ),
    ]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls=[],
    )

    assert "test_something_works" not in unused


def test_pytest_fixture_is_not_flagged():
    functions = [
        FunctionSymbol(
            name="db_session",
            lineno=1,
            end_lineno=3,
            line_count=3,
            decorators=["pytest.fixture"],
        ),
        FunctionSymbol(
            name="anonymous_fixture",
            lineno=5,
            end_lineno=7,
            line_count=3,
            decorators=["fixture"],
        ),
    ]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls=[],
    )

    assert "db_session" not in unused
    assert "anonymous_fixture" not in unused


def test_property_and_framework_decorators_are_not_flagged():
    functions = [
        FunctionSymbol(
            name="value",
            lineno=1,
            end_lineno=3,
            line_count=3,
            decorators=["property"],
        ),
        FunctionSymbol(
            name="from_dict",
            lineno=5,
            end_lineno=7,
            line_count=3,
            decorators=["classmethod"],
        ),
        FunctionSymbol(
            name="helper",
            lineno=9,
            end_lineno=11,
            line_count=3,
            decorators=["staticmethod"],
        ),
        FunctionSymbol(
            name="check_value",
            lineno=13,
            end_lineno=15,
            line_count=3,
            decorators=["pydantic.field_validator"],
        ),
        FunctionSymbol(
            name="do_work",
            lineno=17,
            end_lineno=19,
            line_count=3,
            decorators=["abc.abstractmethod"],
        ),
    ]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls=[],
    )

    assert unused == []


def test_main_entrypoint_is_not_flagged():
    functions = [
        FunctionSymbol(
            name="main",
            lineno=1,
            end_lineno=3,
            line_count=3,
        ),
    ]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls=[],
    )

    assert "main" not in unused


def test_real_dead_function_is_still_flagged():
    functions = [
        FunctionSymbol(
            name="used_function",
            lineno=1,
            end_lineno=3,
            line_count=3,
        ),
        FunctionSymbol(
            name="really_unused_helper",
            lineno=5,
            end_lineno=9,
            line_count=5,
        ),
        FunctionSymbol(
            name="__init__",
            lineno=11,
            end_lineno=13,
            line_count=3,
        ),
        FunctionSymbol(
            name="test_something",
            lineno=15,
            end_lineno=17,
            line_count=3,
        ),
    ]

    calls = ["used_function"]

    unused = DeadCodeDetector().detect_unused_functions(
        functions,
        calls,
    )

    assert unused == ["really_unused_helper"]
