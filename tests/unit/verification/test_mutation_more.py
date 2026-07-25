"""Test per i nuovi operatori di mutazione "slice off-by-one" e
"rimozione chiamata" (statement), e per l'allineamento tra le due
passate (_SiteCollector / _Mutator) su sorgenti che li combinano con
gli operatori gia' esistenti.
"""

import ast

from assist.verification.mutation import MutationEngine, _Mutator, _SiteCollector
from assist.verification.sandbox import SandboxRunner

SLICE_SOURCE = """def head(xs, n):
    return xs[0:n]
"""

SLICE_NO_UPPER_SOURCE = """def tail(xs):
    return xs[1:]
"""

CALL_STMT_SOURCE = """def add_all(xs, out):
    for x in xs:
        out.append(x)
    return out
"""

CALL_AS_EXPR_SOURCE = """def compute(x):
    y = f(x)
    return y
"""

MIXED_SOURCE = """def process(xs, n, out):
    if n > 0:
        out.append(xs[0:n])
    else:
        return xs[1:n]
    return out
"""

STRONG_HEAD_TESTS = """from target import head

def test_head():
    assert head([1, 2, 3], 2) == [1, 2]
"""

WEAK_HEAD_TESTS = """from target import head

def test_head_is_list():
    assert isinstance(head([1, 2, 3], 2), list)
"""


def test_slice_off_by_one_generates_mutant_with_upper_minus_one() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(SLICE_SOURCE)

    descriptions = [m.description for m, _ in mutants]
    assert any("slice off-by-one" in d for d in descriptions)

    slice_mutants = [
        (m, src)
        for m, src in mutants
        if m.description == "slice off-by-one (upper - 1)"
    ]
    assert len(slice_mutants) == 1
    _, mutated_source = slice_mutants[0]
    assert "n - 1" in mutated_source


def test_slice_without_upper_has_no_slice_site() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(SLICE_NO_UPPER_SOURCE)

    descriptions = [m.description for m, _ in mutants]
    assert not any("slice off-by-one" in d for d in descriptions)


def test_call_statement_removal_generates_pass_mutant() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(CALL_STMT_SOURCE)

    descriptions = [m.description for m, _ in mutants]
    assert any(d == "rimozione chiamata" for d in descriptions)

    call_mutants = [
        (m, src) for m, src in mutants if m.description == "rimozione chiamata"
    ]
    assert len(call_mutants) == 1
    _, mutated_source = call_mutants[0]
    assert "pass" in mutated_source
    assert "out.append" not in mutated_source


def test_call_used_as_expression_is_not_a_call_removal_site() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(CALL_AS_EXPR_SOURCE)

    descriptions = [m.description for m, _ in mutants]
    assert "rimozione chiamata" not in descriptions


def test_collector_mutator_alignment_on_mixed_source_with_new_operators() -> None:
    tree = ast.parse(MIXED_SOURCE)

    collector = _SiteCollector()
    collector.visit(tree)

    assert len(collector.sites) > 0

    for index in range(len(collector.sites)):
        mutator = _Mutator(target_index=index)
        mutated_tree = mutator.visit(ast.parse(MIXED_SOURCE))

        assert mutator.applied is True

        ast.fix_missing_locations(mutated_tree)
        mutated_source = ast.unparse(mutated_tree)

        # Non deve sollevare: il sorgente mutato resta sintatticamente
        # valido.
        ast.parse(mutated_source)


def test_end_to_end_slice_mutant_killed_by_strong_tests() -> None:
    engine = MutationEngine(sandbox=SandboxRunner(timeout_seconds=30))

    report = engine.run(
        source=SLICE_SOURCE,
        module_name="target",
        test_source=STRONG_HEAD_TESTS,
    )

    assert report.mutation_score == 1.0
    assert report.survived == 0


def test_end_to_end_slice_mutant_survives_weak_tests() -> None:
    engine = MutationEngine(sandbox=SandboxRunner(timeout_seconds=30))

    report = engine.run(
        source=SLICE_SOURCE,
        module_name="target",
        test_source=WEAK_HEAD_TESTS,
    )

    assert report.total_mutants >= 1
    assert report.survived >= 1
    assert report.mutation_score < 1.0
