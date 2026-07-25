"""Modelli Pydantic per le evidenze di verifica (Proof Engine v1).

Principio: il verdetto non e' un'opinione dell'LLM ma la sintesi di
evidenze deterministiche (test eseguiti, mutanti uccisi/sopravvissuti,
esecuzioni in sandbox). L'LLM spiega le evidenze, non le inventa.
"""

from typing import Literal

from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    """Risultato di una singola esecuzione in sandbox."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class TestRunEvidence(BaseModel):
    """Evidenza di un run di test in sandbox."""

    __test__ = False  # evita la collection di pytest

    label: str
    passed: bool
    tests_collected: int = 0
    tests_failed: int = 0
    failure_summary: str = ""
    sandbox: SandboxResult


class Mutant(BaseModel):
    """Un singolo mutante generato dal MutationEngine."""

    mutant_id: int
    lineno: int
    description: str
    original_snippet: str = ""
    mutated_snippet: str = ""


class MutantResult(BaseModel):
    mutant: Mutant
    killed: bool
    detail: str = ""


class MutationReport(BaseModel):
    """Report del mutation testing: la prova che i test *provano* qualcosa.

    mutation_score = mutanti uccisi / mutanti totali.
    Un punteggio basso significa che i test non verificano il
    comportamento reale del codice (test-bugia).
    """

    total_mutants: int = 0
    killed: int = 0
    survived: int = 0
    mutation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    surviving_mutants: list[MutantResult] = Field(default_factory=list)
    skipped_reason: str = ""


class EvidenceBundle(BaseModel):
    """Tutte le evidenze raccolte dalla pipeline su un file."""

    target_file: str
    module_name: str
    syntax_ok: bool = True
    syntax_error: str = ""
    baseline_tests: TestRunEvidence | None = None
    boundary_tests: TestRunEvidence | None = None
    boundary_tests_source: str = ""
    property_tests: TestRunEvidence | None = None
    property_tests_source: str = ""
    mutation: MutationReport | None = None
    dependencies: list[str] = Field(default_factory=list)
    discovered_tests_path: str = ""
    notes: list[str] = Field(default_factory=list)


VerdictStatus = Literal["pass", "warn", "fail"]


class Verdict(BaseModel):
    """Verdetto finale: stato deciso deterministicamente dalle evidenze,
    spiegazione e fix proposti dal modello forte."""

    status: VerdictStatus
    reasons: list[str] = Field(default_factory=list)
    explanation: str = ""
    proposed_fix: str = ""
    fix_validated: bool = False
    mutation_score: float | None = None


class VerificationOutput(BaseModel):
    verdict: Verdict
    evidence: EvidenceBundle
    report_markdown: str = ""
