"""Test estesi per il MutationEngine.

Coprono il nuovo operatore "negazione condizione if", la selezione
per righe target (`target_lines`) e l'allineamento tra le due
passate (_SiteCollector / _Mutator) su sorgenti con costrutti misti.
"""

import ast

from assist.verification.mutation import MutationEngine, _Mutator, _SiteCollector
from assist.verification.sandbox import SandboxRunner

IF_SOURCE = """def check(x):
    if x > 10:
        return True
    return False
"""

WEAK_IF_TESTS = """from target import check

def test_obvious():
    assert check(100) is True
"""

STRONG_IF_TESTS = """from target import check

def test_boundary():
    assert check(11) is True
    assert check(10) is False
    assert check(9) is False
"""

MIXED_SOURCE = """def classify(x, y):
    threshold = 10
    active = True
    if x > threshold:
        return active and y
    return False
"""


def test_if_negation_generates_mutant_with_not() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(IF_SOURCE)

    descriptions = [m.description for m, _ in mutants]
    assert any("negazione condizione if" in d for d in descriptions)

    if_mutants = [
        (m, src)
        for m, src in mutants
        if m.description == "negazione condizione if"
    ]
    assert len(if_mutants) == 1
    _, mutated_source = if_mutants[0]
    assert "not" in mutated_source


def test_target_lines_filters_mutants() -> None:
    engine = MutationEngine()

    all_mutants = engine.generate_mutants(IF_SOURCE)
    all_linenos = {m.lineno for m, _ in all_mutants}
    assert len(all_linenos) > 1  # il sorgente ha siti su piu' righe

    target_lineno = min(all_linenos)
    filtered = engine.generate_mutants(IF_SOURCE, target_lines={target_lineno})

    assert len(filtered) >= 1
    assert all(m.lineno == target_lineno for m, _ in filtered)
    assert len(filtered) < len(all_mutants)


def test_target_lines_empty_set_yields_no_mutants() -> None:
    engine = MutationEngine()

    filtered = engine.generate_mutants(IF_SOURCE, target_lines=set())

    assert filtered == []


def test_collector_mutator_alignment_on_mixed_source() -> None:
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


def test_end_to_end_if_negation_killed_by_strong_tests() -> None:
    engine = MutationEngine(sandbox=SandboxRunner(timeout_seconds=30))

    report = engine.run(
        source=IF_SOURCE,
        module_name="target",
        test_source=STRONG_IF_TESTS,
    )

    assert report.mutation_score == 1.0
    assert report.survived == 0


def test_end_to_end_if_negation_survives_weak_tests() -> None:
    engine = MutationEngine(sandbox=SandboxRunner(timeout_seconds=30))

    report = engine.run(
        source=IF_SOURCE,
        module_name="target",
        test_source=WEAK_IF_TESTS,
    )

    assert report.total_mutants >= 1
    assert report.survived >= 1
    assert report.mutation_score < 1.0


def test_descriptions_match_actual_mutation_on_nested_source():
    """Regressione: su costrutti annidati (Compare contenente BinOp)
    la descrizione di ogni mutante deve corrispondere alla mutazione
    realmente applicata, non a quella di un altro sito."""
    from assist.verification.mutation import MutationEngine

    source = "def f(a, b):\n    return a < b + 1\n"

    for mutant, mutated in MutationEngine().generate_mutants(source):
        body = mutated.splitlines()[-1]

        if "confronto" in mutant.description:
            assert "<=" in body
        elif "aritmetico" in mutant.description:
            assert "b - 1" in body
        elif "off-by-one" in mutant.description:
            assert "+ 2" in body


def test_boolop_children_counted_once():
    """Regressione: i figli di un BoolOp (Compare, Constant) devono
    generare UN solo sito ciascuno — un doppio generic_visit nel
    collector li duplicava disallineando collector e mutator."""
    import ast

    from assist.verification.mutation import _SiteCollector

    source = "def f(t, flag):\n    if t > 100 and flag:\n        return 1\n    return 0\n"

    collector = _SiteCollector()
    collector.visit(ast.parse(source))

    descriptions = [d for _, d in collector.sites]

    assert descriptions.count("operatore di confronto > -> >=") == 1
    assert descriptions.count("costante intera 100 -> 101 (off-by-one)") == 1
