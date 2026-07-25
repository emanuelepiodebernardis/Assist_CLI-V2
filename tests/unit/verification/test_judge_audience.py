"""Test per il supporto audience ("dev" / "non-dev") in EvidenceJudge."""

import pytest

from assist.llm.base import LLMClient
from assist.llm.mock_client import MockLLMClient
from assist.verification.evidence import (
    EvidenceBundle,
    Mutant,
    MutantResult,
    MutationReport,
    SandboxResult,
    TestRunEvidence,
)
from assist.verification.judge import EvidenceJudge


def _sandbox_ok() -> SandboxResult:
    return SandboxResult(exit_code=0)


class _CapturingLLMClient(LLMClient):
    """LLM finto che cattura prompt e system ricevuti."""

    def __init__(self, fixture: str = "Spiegazione mock.") -> None:
        self.fixture = fixture
        self.last_prompt: str = ""
        self.last_system: str = ""

    def complete(self, prompt: str, system: str = "") -> str:
        self.last_prompt = prompt
        self.last_system = system
        return self.fixture


def _low_mutation_evidence() -> EvidenceBundle:
    """Evidenze con mutation score basso (status warn) e un sopravvissuto."""
    return EvidenceBundle(
        target_file="x.py",
        module_name="x",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=True,
            sandbox=_sandbox_ok(),
        ),
        mutation=MutationReport(
            total_mutants=10,
            killed=3,
            survived=7,
            mutation_score=0.3,
            surviving_mutants=[
                MutantResult(
                    mutant=Mutant(
                        mutant_id=1,
                        lineno=42,
                        description="cambio operatore",
                        original_snippet="a > b",
                    ),
                    killed=False,
                )
            ],
        ),
    )


def _failing_evidence() -> EvidenceBundle:
    """Evidenze con test esistenti falliti (status fail)."""
    return EvidenceBundle(
        target_file="x.py",
        module_name="x",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_failed=2,
            sandbox=SandboxResult(exit_code=1),
        ),
    )


def test_invalid_audience_raises_value_error() -> None:
    with pytest.raises(ValueError):
        EvidenceJudge(llm=MockLLMClient(), audience="marketing")


def test_default_audience_dev_behaves_like_before() -> None:
    judge = EvidenceJudge(
        llm=MockLLMClient(fixture="Spiegazione mock."),
        mutation_threshold=0.60,
    )

    assert judge.audience == "dev"

    verdict = judge.judge(_low_mutation_evidence())

    assert verdict.status == "warn"
    assert verdict.explanation


def test_non_dev_system_avoids_jargon_and_translates_labels() -> None:
    llm = _CapturingLLMClient()
    judge = EvidenceJudge(llm=llm, mutation_threshold=0.60, audience="non-dev")

    verdict = judge.judge(_low_mutation_evidence(), source="print('hi')\n")

    assert verdict.status == "warn"
    assert "mutante" not in llm.last_system.lower()
    assert "Controllo qualita' dei test" in llm.last_prompt
    assert "NON RILEVATO" in llm.last_prompt
    # Con status warn il sorgente non serve (non c'e' fix da applicare).
    assert "Sorgente del file" not in llm.last_prompt


def test_non_dev_with_fail_and_source_includes_source_for_fix() -> None:
    llm = _CapturingLLMClient()
    judge = EvidenceJudge(llm=llm, mutation_threshold=0.60, audience="non-dev")

    verdict = judge.judge(_failing_evidence(), source="def f(): pass\n")

    assert verdict.status == "fail"
    assert "Sorgente del file" in llm.last_prompt
    assert "def f(): pass" in llm.last_prompt


def test_status_identical_between_dev_and_non_dev() -> None:
    evidence = _low_mutation_evidence()

    dev_judge = EvidenceJudge(
        llm=MockLLMClient(fixture="ok"),
        mutation_threshold=0.60,
        audience="dev",
    )
    non_dev_judge = EvidenceJudge(
        llm=MockLLMClient(fixture="ok"),
        mutation_threshold=0.60,
        audience="non-dev",
    )

    dev_verdict = dev_judge.judge(evidence)
    non_dev_verdict = non_dev_judge.judge(evidence)

    assert dev_verdict.status == non_dev_verdict.status
    assert dev_verdict.reasons == non_dev_verdict.reasons
