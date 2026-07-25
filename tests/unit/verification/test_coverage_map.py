"""Test per `CoverageMap` / `build_coverage_map` e per l'integrazione
del per-test coverage in `MutationEngine.run` (Fase A della roadmap).
"""

from assist.verification.coverage_map import CoverageMap, build_coverage_map
from assist.verification.evidence import SandboxResult
from assist.verification.mutation import MutationEngine
from assist.verification.sandbox import SandboxRunner

TWO_FUNCTIONS_SOURCE = (
    "def func_a(x):\n"
    "    return x + 1\n"
    "\n\n"
    "def func_b(x):\n"
    "    return x - 1\n"
)

TESTS_ONE_PER_FUNCTION = (
    "from target import func_a, func_b\n\n\n"
    "def test_func_a():\n"
    "    assert func_a(1) == 2\n\n\n"
    "def test_func_b():\n"
    "    assert func_b(1) == 0\n"
)

TESTS_ONLY_FUNC_A = (
    "from target import func_a\n\n\n"
    "def test_func_a():\n"
    "    assert func_a(1) == 2\n"
)


class _NoMarkerSandbox:
    """Sandbox finta il cui `run_script` non produce i marker attesi
    (simula coverage/pytest-cov assenti o un crash prima della stampa)."""

    def run_script(self, files: dict[str, str], entry: str) -> SandboxResult:
        return SandboxResult(exit_code=0, stdout="nessun marker qui dentro")


class _CountingSandbox:
    """Sandbox finta: conta le chiamate e fa "sopravvivere" ogni
    mutante (exit_code=1 -> test falliti -> mutante ucciso)."""

    def __init__(self) -> None:
        self.calls = 0

    def run_pytest(self, files: dict[str, str], **kwargs: object) -> SandboxResult:
        self.calls += 1
        return SandboxResult(exit_code=1)


def test_build_coverage_map_line_is_covered_only_by_its_own_test() -> None:
    sandbox = SandboxRunner(timeout_seconds=30)

    coverage_map = build_coverage_map(
        source=TWO_FUNCTIONS_SOURCE,
        module_name="target",
        test_source=TESTS_ONE_PER_FUNCTION,
        test_file_name="test_target.py",
        sandbox=sandbox,
    )

    assert coverage_map.available is True

    # La riga di func_a (return x + 1, riga 2) e' coperta SOLO dal
    # test dedicato a func_a, non da quello di func_b.
    assert coverage_map.tests_for_line(2) == {"test_target.py::test_func_a"}


def test_build_coverage_map_uncovered_line_has_no_tests() -> None:
    sandbox = SandboxRunner(timeout_seconds=30)

    coverage_map = build_coverage_map(
        source=TWO_FUNCTIONS_SOURCE,
        module_name="target",
        test_source=TESTS_ONLY_FUNC_A,
        test_file_name="test_target.py",
        sandbox=sandbox,
    )

    assert coverage_map.available is True
    # func_b non e' mai chiamata: la sua riga (return x - 1, riga 6)
    # non ha alcun test che la copre.
    assert coverage_map.tests_for_line(6) == set()
    assert "test_target.py::test_func_a" in coverage_map.all_tests()


REAL_SOURCE = (
    "def is_adult(age):\n"
    "    return age >= 18\n"
    "\n\n"
    "def unchecked(x):\n"
    "    return x + 1\n"
)

STRONG_IS_ADULT_TESTS = (
    "from target import is_adult\n\n\n"
    "def test_boundary():\n"
    "    assert is_adult(18) is True\n"
    "    assert is_adult(17) is False\n\n\n"
    "def test_obvious():\n"
    "    assert is_adult(50) is True\n"
    "    assert is_adult(3) is False\n"
)


def test_run_with_coverage_map_skips_uncovered_function_and_reduces_runs() -> None:
    build_sandbox = SandboxRunner(timeout_seconds=30)
    coverage_map = build_coverage_map(
        source=REAL_SOURCE,
        module_name="target",
        test_source=STRONG_IS_ADULT_TESTS,
        test_file_name="test_target.py",
        sandbox=build_sandbox,
    )
    assert coverage_map.available is True

    sandbox_with_cov = SandboxRunner(timeout_seconds=30)
    engine_with_cov = MutationEngine(sandbox=sandbox_with_cov)
    report_with_cov = engine_with_cov.run(
        source=REAL_SOURCE,
        module_name="target",
        test_source=STRONG_IS_ADULT_TESTS,
        coverage_map=coverage_map,
    )

    sandbox_without_cov = SandboxRunner(timeout_seconds=30)
    engine_without_cov = MutationEngine(sandbox=sandbox_without_cov)
    report_without_cov = engine_without_cov.run(
        source=REAL_SOURCE,
        module_name="target",
        test_source=STRONG_IS_ADULT_TESTS,
    )

    assert report_with_cov.total_mutants == report_without_cov.total_mutants

    # I mutanti sulla funzione non coperta (unchecked, riga 6) sono
    # "sopravvissuti" senza eseguire alcun test.
    uncovered = [r for r in report_with_cov.surviving_mutants if r.mutant.lineno == 6]
    assert len(uncovered) == 2
    assert all(r.detail == "nessun test copre la riga" for r in uncovered)

    # I mutanti sulla funzione testata (riga 2) vengono comunque
    # rilevati (uccisi) usando solo i test selezionati dalla mappa.
    assert all(r.mutant.lineno != 2 for r in report_with_cov.surviving_mutants)

    # Meno chiamate reali alla sandbox rispetto al run senza mappa di
    # copertura: i mutanti sulla riga non coperta non innescano alcuna
    # esecuzione di pytest.
    assert sandbox_with_cov.runs < sandbox_without_cov.runs
    assert sandbox_with_cov.runs == 2
    assert sandbox_without_cov.runs == report_without_cov.total_mutants


def test_build_coverage_map_fallback_when_markers_missing() -> None:
    coverage_map = build_coverage_map(
        source="def f(x):\n    return x\n",
        module_name="target",
        test_source="def test_f():\n    assert True\n",
        test_file_name="test_target.py",
        sandbox=_NoMarkerSandbox(),
    )

    assert coverage_map.available is False
    assert coverage_map.tests_for_line(2) == set()
    assert coverage_map.all_tests() == set()


def test_run_with_unavailable_coverage_map_behaves_like_without() -> None:
    source = "def is_adult(age):\n    return age >= 18\n"
    tests = "def test_noop():\n    assert True\n"

    sandbox_a = _CountingSandbox()
    engine_a = MutationEngine(sandbox=sandbox_a)
    report_a = engine_a.run(source=source, module_name="target", test_source=tests)

    sandbox_b = _CountingSandbox()
    engine_b = MutationEngine(sandbox=sandbox_b)
    not_available = CoverageMap(available=False)
    report_b = engine_b.run(
        source=source,
        module_name="target",
        test_source=tests,
        coverage_map=not_available,
    )

    assert sandbox_b.calls == sandbox_a.calls == report_a.total_mutants
    assert report_b.total_mutants == report_a.total_mutants
    assert report_b.survived == report_a.survived
