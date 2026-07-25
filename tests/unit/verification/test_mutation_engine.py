from assist.verification.mutation import MutationEngine
from assist.verification.sandbox import SandboxRunner

SOURCE = """def is_adult(age):
    return age >= 18
"""

WEAK_TESTS = """from target import is_adult

def test_obvious():
    assert is_adult(50) is True
    assert is_adult(3) is False
"""

STRONG_TESTS = """from target import is_adult

def test_boundary():
    assert is_adult(18) is True
    assert is_adult(17) is False

def test_obvious():
    assert is_adult(50) is True
    assert is_adult(3) is False
"""


def test_generates_mutants():
    engine = MutationEngine()

    mutants = engine.generate_mutants(SOURCE)

    assert len(mutants) >= 2

    descriptions = [m.description for m, _ in mutants]

    assert any(">=" in d for d in descriptions)
    assert any("off-by-one" in d for d in descriptions)


def test_weak_tests_let_mutants_survive():
    engine = MutationEngine(
        sandbox=SandboxRunner(timeout_seconds=30)
    )

    report = engine.run(
        source=SOURCE,
        module_name="target",
        test_source=WEAK_TESTS,
    )

    assert report.total_mutants >= 2
    assert report.survived >= 1
    assert report.mutation_score < 1.0


def test_strong_tests_kill_boundary_mutants():
    engine = MutationEngine(
        sandbox=SandboxRunner(timeout_seconds=30)
    )

    report = engine.run(
        source=SOURCE,
        module_name="target",
        test_source=STRONG_TESTS,
    )

    assert report.mutation_score == 1.0
    assert report.survived == 0


def test_no_mutable_sites():
    engine = MutationEngine()

    report = engine.run(
        source="x = None\n",
        module_name="target",
        test_source="def test_noop():\n    assert True\n",
    )

    assert report.skipped_reason
