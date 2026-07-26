"""Test per il limite ``max_input_chars`` sulle evidenze rese nel prompt."""

from __future__ import annotations

from assist.llm.base import LLMClient
from assist.verification.evidence import (
    EvidenceBundle,
    SandboxResult,
    TestRunEvidence,
)
from assist.verification.judge import EvidenceJudge

# Margine per l'overhead fisso del template del prompt (target_file,
# status, testo dei "Compiti", fix_instruction...): non dipende da
# max_input_chars ne' dalla lunghezza del sorgente.
_TEMPLATE_MARGIN = 700


class _CapturingLLMClient(LLMClient):
    """LLM finto che cattura il prompt ricevuto."""

    def __init__(self, fixture: str = "Spiegazione mock.") -> None:
        self.fixture = fixture
        self.last_prompt: str = ""

    def complete(self, prompt: str, system: str = "") -> str:
        self.last_prompt = prompt
        return self.fixture


def _sandbox_ok() -> SandboxResult:
    return SandboxResult(exit_code=0)


def _failing_evidence() -> EvidenceBundle:
    """Evidenze con test falliti (status fail): il sorgente entra nel prompt."""
    return EvidenceBundle(
        target_file="x.py",
        module_name="x",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_failed=1,
            sandbox=SandboxResult(exit_code=1),
        ),
    )


def test_small_max_input_chars_truncates_prompt_with_note() -> None:
    llm = _CapturingLLMClient()
    judge = EvidenceJudge(llm=llm, max_input_chars=500)

    long_source = "x = 1\n" * 2000  # molto più di 500 caratteri

    judge.judge(_failing_evidence(), source=long_source)

    prompt = llm.last_prompt

    assert len(prompt) <= 500 + _TEMPLATE_MARGIN
    assert "...(evidenze troncate)" in prompt


def test_default_max_input_chars_includes_source_beyond_old_6000_limit() -> None:
    llm = _CapturingLLMClient()
    judge = EvidenceJudge(llm=llm)  # default max_input_chars=24000

    source_10k = "y = 2\n" * 1700  # ~10200 caratteri, oltre il vecchio limite 6000
    assert len(source_10k) > 10000

    judge.judge(_failing_evidence(), source=source_10k)

    prompt = llm.last_prompt

    # Il vecchio limite fisso era 6000: verifichiamo che il sorgente non
    # sia stato troncato a 6000 caratteri e che compaia per intero.
    assert source_10k in prompt
    assert "...(evidenze troncate)" not in prompt


def test_custom_max_input_chars_is_used_instead_of_default() -> None:
    llm = _CapturingLLMClient()
    judge = EvidenceJudge(llm=llm, max_input_chars=8000)

    assert judge.max_input_chars == 8000

    source_7k = "z = 3\n" * 1200  # ~7200 caratteri, sotto 8000 ma sopra 6000
    assert 6000 < len(source_7k) < 8000

    judge.judge(_failing_evidence(), source=source_7k)

    prompt = llm.last_prompt

    assert source_7k in prompt
