"""Integrazione end-to-end della pipeline di verifica (Fase 1).

Copre: dipendenze multi-file in sandbox, auto-discovery dei test,
fix loop validato (fix accettato solo se i test rossi passano).
"""

from pathlib import Path

from assist.llm.base import LLMClient
from assist.verification.pipeline import VerificationPipeline

HELPERS = """def tax_rate(income):
    if income > 50000:
        return 0.35
    return 0.20
"""

# BUG: usa il segno sbagliato — sottrae la tassa due volte
BUGGY = """from helpers import tax_rate


def net_income(income):
    tax = income * tax_rate(income)
    return income - tax - tax
"""

FIXED = """from helpers import tax_rate


def net_income(income):
    tax = income * tax_rate(income)
    return income - tax
"""

TESTS = """from salary import net_income


def test_low_income():
    assert net_income(10000) == 8000.0


def test_high_income():
    assert net_income(100000) == 65000.0
"""


class _ScriptedLLM(LLMClient):
    """LLM finto che risponde con fixture in sequenza."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str, system: str = "") -> str:
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return "nessuna risposta"


def _setup_project(tmp_path: Path) -> Path:
    (tmp_path / "helpers.py").write_text(HELPERS, encoding="utf-8")
    target = tmp_path / "salary.py"
    target.write_text(BUGGY, encoding="utf-8")
    # auto-discovery: test_<stem>.py nella stessa directory
    (tmp_path / "test_salary.py").write_text(TESTS, encoding="utf-8")
    return target


def test_multifile_discovery_and_validated_fix(tmp_path):
    target = _setup_project(tmp_path)

    strong = _ScriptedLLM(
        responses=[
            # 1) spiegazione del judge
            "I test falliscono per il doppio addebito della tassa.",
            # 2) primo fix richiesto dal fix loop: CORRETTO
            f"```python\n{FIXED}```",
        ]
    )

    pipeline = VerificationPipeline(
        fast_llm=_ScriptedLLM(responses=["niente codice"]),
        strong_llm=strong,
        sandbox_timeout=30,
        max_mutants=10,
    )

    result = pipeline.run(file_path=str(target))

    evidence = result.evidence

    # dipendenze multi-file raccolte e usate in sandbox
    assert evidence.dependencies == ["helpers.py"]

    # test scoperti automaticamente senza --tests
    assert evidence.discovered_tests_path.endswith("test_salary.py")

    # i test baseline falliscono (bug reale)
    assert evidence.baseline_tests is not None
    assert not evidence.baseline_tests.passed
    assert result.verdict.status == "fail"

    # il fix e' stato validato in sandbox, non solo proposto
    assert result.verdict.fix_validated is True
    assert "return income - tax" in result.verdict.proposed_fix
    assert "tax - tax" not in result.verdict.proposed_fix
    assert "Fix validato in sandbox" in result.report_markdown


def test_fix_never_accepted_without_green_tests(tmp_path):
    target = _setup_project(tmp_path)

    strong = _ScriptedLLM(
        responses=[
            "Spiegazione.",
            # fix sempre sbagliati: il loop non deve mai accettarli
            f"```python\n{BUGGY}```",
            f"```python\n{BUGGY}```",
            f"```python\n{BUGGY}```",
        ]
    )

    pipeline = VerificationPipeline(
        fast_llm=_ScriptedLLM(responses=["niente codice"]),
        strong_llm=strong,
        sandbox_timeout=30,
        max_mutants=5,
        max_fix_iterations=2,
    )

    result = pipeline.run(file_path=str(target))

    assert result.verdict.status == "fail"
    assert result.verdict.fix_validated is False
    assert any(
        "Nessun fix validato" in note
        for note in result.evidence.notes
    )


def test_target_lines_limits_mutation(tmp_path):
    target = _setup_project(tmp_path)
    # correggi il bug per avere baseline verde
    target.write_text(FIXED, encoding="utf-8")

    pipeline = VerificationPipeline(
        fast_llm=_ScriptedLLM(responses=["niente codice"]),
        strong_llm=_ScriptedLLM(responses=["Spiegazione."]),
        sandbox_timeout=30,
        max_mutants=20,
    )

    full = pipeline.run(file_path=str(target))
    limited = pipeline.run(
        file_path=str(target),
        target_lines={5},  # solo la riga del calcolo tassa
    )

    assert full.evidence.mutation is not None
    assert limited.evidence.mutation is not None
    assert (
        limited.evidence.mutation.total_mutants
        < full.evidence.mutation.total_mutants
    )


def test_structured_failure_summary(tmp_path):
    """Il parser JUnit XML produce un summary strutturato
    nome-test::messaggio, non piu' regex sull'output."""
    target = _setup_project(tmp_path)

    pipeline = VerificationPipeline(
        fast_llm=_ScriptedLLM(responses=["niente codice"]),
        strong_llm=_ScriptedLLM(responses=["Spiegazione.", "no fix"]),
        sandbox_timeout=30,
        max_mutants=5,
        max_fix_iterations=1,
    )

    result = pipeline.run(file_path=str(target))

    baseline = result.evidence.baseline_tests

    assert baseline is not None
    assert not baseline.passed
    assert baseline.tests_collected == 2
    assert baseline.tests_failed == 2
    # summary strutturato: contiene i nomi dei test falliti
    assert "test_low_income" in baseline.failure_summary
    assert "test_high_income" in baseline.failure_summary


class _FlakyScriptedPipeline(VerificationPipeline):
    """Pipeline con _run_tests scriptato per i boundary:
    primo run fallito, secondo run passato (test flaky)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boundary_runs = 0

    def _run_tests(
        self, source, module_name, test_source, label, extra_files=None
    ):
        run = super()._run_tests(
            source, module_name, test_source, label, extra_files
        )

        if label == "boundary":
            self.boundary_runs += 1
            # primo run: forza il fallimento; secondo: esito reale
            if self.boundary_runs == 1:
                run = run.model_copy(update={"passed": False})

        return run


BOUNDARY_OK = """```python
from salary import net_income


def test_boundary_zero():
    assert net_income(0) == 0.0
```"""


def test_flaky_boundary_tests_are_quarantined(tmp_path):
    target = _setup_project(tmp_path)
    target.write_text(FIXED, encoding="utf-8")

    pipeline = _FlakyScriptedPipeline(
        fast_llm=_ScriptedLLM(responses=[BOUNDARY_OK]),
        strong_llm=_ScriptedLLM(responses=["Spiegazione."]),
        sandbox_timeout=30,
        max_mutants=5,
    )

    result = pipeline.run(file_path=str(target))

    # due run boundary eseguiti (originale + conferma)
    assert pipeline.boundary_runs == 2

    # quarantena: esclusi dal verdetto, con nota esplicita
    assert result.evidence.boundary_tests is None
    assert any(
        "flaky" in note for note in result.evidence.notes
    )
    # il verdetto non e' fail a causa dei test instabili
    assert result.verdict.status != "fail"
