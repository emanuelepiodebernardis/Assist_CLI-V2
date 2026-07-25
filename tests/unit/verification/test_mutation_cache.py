"""Test per il mutatore "rimozione return anticipato" e per la
cache dei risultati per mutante di `MutationEngine.run`.
"""

import ast

from assist.verification.evidence import SandboxResult
from assist.verification.mutation import MutationEngine, _Mutator, _SiteCollector

EARLY_RETURN_SOURCE = """def check(x):
    if x < 0:
        return None
    y = x + 1
    return y
"""

MIXED_WITH_EARLY_RETURN_SOURCE = """def classify(x, y):
    threshold = 10
    if x < 0:
        return None
    if x > threshold:
        return x + 1
    return y == threshold
"""


class _CountingSandbox:
    """Sandbox finta: conta le chiamate e fa "sopravvivere" ogni
    mutante (exit_code=1 -> test falliti -> mutante ucciso)."""

    def __init__(self) -> None:
        self.calls = 0

    def run_pytest(self, files: dict[str, str], **kwargs: object) -> SandboxResult:
        self.calls += 1
        return SandboxResult(exit_code=1)


def test_early_return_generates_mutant_but_final_return_does_not() -> None:
    engine = MutationEngine()

    mutants = engine.generate_mutants(EARLY_RETURN_SOURCE)

    early_return_mutants = [
        (m, src)
        for m, src in mutants
        if m.description == "rimozione return anticipato"
    ]
    assert len(early_return_mutants) == 1

    mutant, mutated_source = early_return_mutants[0]
    assert mutant.lineno == 3
    assert "pass" in mutated_source
    # Il return finale (ultimo statement del body) resta intatto:
    # non deve comparire "pass" al posto suo, la funzione deve
    # ancora contenere "return y".
    assert "return y" in mutated_source


def test_final_return_is_not_mutable() -> None:
    source = "def f(x):\n    return x\n"

    engine = MutationEngine()
    mutants = engine.generate_mutants(source)

    descriptions = [m.description for m, _ in mutants]
    assert "rimozione return anticipato" not in descriptions


def test_collector_mutator_alignment_with_early_return() -> None:
    tree = ast.parse(MIXED_WITH_EARLY_RETURN_SOURCE)

    collector = _SiteCollector()
    collector.visit(tree)

    assert len(collector.sites) > 0
    assert any(desc == "rimozione return anticipato" for _, desc in collector.sites)

    for index in range(len(collector.sites)):
        mutator = _Mutator(target_index=index)
        mutated_tree = mutator.visit(ast.parse(MIXED_WITH_EARLY_RETURN_SOURCE))

        assert mutator.applied is True

        ast.fix_missing_locations(mutated_tree)
        mutated_source = ast.unparse(mutated_tree)

        # Non deve sollevare: il sorgente mutato resta sintatticamente
        # valido.
        ast.parse(mutated_source)


SOURCE = "def is_adult(age):\n    return age >= 18\n"
TESTS = "def test_noop():\n    assert True\n"


def test_repeated_run_uses_cache_and_skips_sandbox() -> None:
    sandbox = _CountingSandbox()
    engine = MutationEngine(sandbox=sandbox)

    first = engine.run(source=SOURCE, module_name="target", test_source=TESTS)
    calls_after_first = sandbox.calls
    assert calls_after_first == first.total_mutants
    assert engine.cache_hits == 0

    second = engine.run(source=SOURCE, module_name="target", test_source=TESTS)

    assert sandbox.calls == calls_after_first  # nessuna nuova chiamata
    assert engine.cache_hits == second.total_mutants
    assert second.total_mutants == first.total_mutants


def test_shared_cache_works_across_engine_instances() -> None:
    shared_cache: dict[str, bool] = {}

    sandbox_a = _CountingSandbox()
    engine_a = MutationEngine(sandbox=sandbox_a, cache=shared_cache)
    report_a = engine_a.run(source=SOURCE, module_name="target", test_source=TESTS)

    assert sandbox_a.calls == report_a.total_mutants
    assert engine_a.cache_hits == 0

    sandbox_b = _CountingSandbox()
    engine_b = MutationEngine(sandbox=sandbox_b, cache=shared_cache)
    report_b = engine_b.run(source=SOURCE, module_name="target", test_source=TESTS)

    assert sandbox_b.calls == 0  # tutto trovato nella cache condivisa
    assert engine_b.cache_hits == report_b.total_mutants
    assert report_b.total_mutants == report_a.total_mutants


def test_different_test_source_is_a_cache_miss() -> None:
    shared_cache: dict[str, bool] = {}

    sandbox_a = _CountingSandbox()
    engine_a = MutationEngine(sandbox=sandbox_a, cache=shared_cache)
    engine_a.run(source=SOURCE, module_name="target", test_source=TESTS)

    other_tests = "def test_other():\n    assert 1 == 1\n"

    sandbox_b = _CountingSandbox()
    engine_b = MutationEngine(sandbox=sandbox_b, cache=shared_cache)
    report_b = engine_b.run(
        source=SOURCE, module_name="target", test_source=other_tests
    )

    # test_source diverso -> chiave di cache diversa -> nessun hit,
    # la sandbox viene rieseguita per ogni mutante.
    assert sandbox_b.calls == report_b.total_mutants
    assert engine_b.cache_hits == 0
