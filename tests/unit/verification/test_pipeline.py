from pathlib import Path

from assist.llm.mock_client import MockLLMClient
from assist.verification.pipeline import VerificationPipeline

BUGGY_SOURCE = """def apply_discount(price, percent):
    # BUG: soglia sbagliata, sconto oltre 100% ammesso
    if percent > 100:
        percent = 100
    return price - price * percent / 100


def is_valid_percent(percent):
    return 0 <= percent <= 100
"""

BASELINE_TESTS = """from buggy_module import apply_discount, is_valid_percent


def test_discount_half():
    assert apply_discount(100, 50) == 50.0


def test_valid_percent():
    assert is_valid_percent(50) is True
    assert is_valid_percent(150) is False
"""

FAILING_TESTS = """from buggy_module import apply_discount


def test_discount_never_negative():
    assert apply_discount(100, 200) >= 0
    # con percent=200 il clamp funziona, ma percent=101 no... anzi si.
    assert apply_discount(100, 100) == 0.0


def test_wrong_expectation():
    assert apply_discount(100, 10) == 80.0
"""

BOUNDARY_RESPONSE = """```python
from buggy_module import apply_discount, is_valid_percent


def test_zero_percent():
    assert apply_discount(100, 0) == 100.0


def test_full_percent():
    assert apply_discount(100, 100) == 0.0


def test_percent_boundaries():
    assert is_valid_percent(0) is True
    assert is_valid_percent(100) is True
    assert is_valid_percent(101) is False
    assert is_valid_percent(-1) is False
```"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    target = tmp_path / name
    target.write_text(content, encoding="utf-8")
    return target


def _pipeline(boundary_fixture: str = BOUNDARY_RESPONSE):
    return VerificationPipeline(
        fast_llm=MockLLMClient(fixture=boundary_fixture),
        strong_llm=MockLLMClient(fixture="Spiegazione mock."),
        sandbox_timeout=30,
        max_mutants=20,
    )


def test_pipeline_with_passing_tests(tmp_path):
    source_file = _write(tmp_path, "buggy_module.py", BUGGY_SOURCE)
    tests_file = _write(tmp_path, "test_buggy.py", BASELINE_TESTS)

    result = _pipeline().run(
        file_path=str(source_file),
        tests_path=str(tests_file),
    )

    assert result.evidence.syntax_ok
    assert result.evidence.baseline_tests is not None
    assert result.evidence.baseline_tests.passed
    assert result.evidence.boundary_tests is not None
    assert result.evidence.mutation is not None
    assert result.evidence.mutation.total_mutants > 0
    assert result.verdict.status in ("pass", "warn")
    assert "Verifica" in result.report_markdown


def test_pipeline_detects_failing_tests(tmp_path):
    source_file = _write(tmp_path, "buggy_module.py", BUGGY_SOURCE)
    tests_file = _write(tmp_path, "test_buggy.py", FAILING_TESTS)

    result = _pipeline(boundary_fixture="niente codice").run(
        file_path=str(source_file),
        tests_path=str(tests_file),
    )

    assert result.evidence.baseline_tests is not None
    assert not result.evidence.baseline_tests.passed
    assert result.verdict.status == "fail"


def test_pipeline_syntax_error(tmp_path):
    source_file = _write(
        tmp_path, "broken.py", "def broken(:\n    pass\n"
    )

    result = _pipeline().run(file_path=str(source_file))

    assert not result.evidence.syntax_ok
    assert result.verdict.status == "fail"


def test_pipeline_no_tests_is_warn(tmp_path):
    source_file = _write(tmp_path, "buggy_module.py", BUGGY_SOURCE)

    result = _pipeline(boundary_fixture="niente codice").run(
        file_path=str(source_file)
    )

    assert result.evidence.boundary_tests is None
    assert result.verdict.status == "warn"
