from assist.llm.mock_client import MockLLMClient
from assist.verification.evidence import (
    EvidenceBundle,
    MutationReport,
    SandboxResult,
    TestRunEvidence,
)
from assist.verification.judge import EvidenceJudge


def _sandbox_ok():
    return SandboxResult(exit_code=0)


def _sandbox_fail():
    return SandboxResult(exit_code=1)


def _judge():
    return EvidenceJudge(
        llm=MockLLMClient(fixture="Spiegazione mock."),
        mutation_threshold=0.60,
    )


def test_syntax_error_is_fail():
    evidence = EvidenceBundle(
        target_file="x.py",
        module_name="x",
        syntax_ok=False,
        syntax_error="riga 1: invalid syntax",
    )

    verdict = _judge().judge(evidence)

    assert verdict.status == "fail"


def test_failing_tests_is_fail():
    evidence = EvidenceBundle(
        target_file="x.py",
        module_name="x",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_failed=2,
            sandbox=_sandbox_fail(),
        ),
    )

    verdict = _judge().judge(evidence)

    assert verdict.status == "fail"


def test_low_mutation_score_is_warn():
    evidence = EvidenceBundle(
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
        ),
    )

    verdict = _judge().judge(evidence)

    assert verdict.status == "warn"
    assert verdict.mutation_score == 0.3


def test_all_green_is_pass():
    evidence = EvidenceBundle(
        target_file="x.py",
        module_name="x",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=True,
            sandbox=_sandbox_ok(),
        ),
        mutation=MutationReport(
            total_mutants=10,
            killed=9,
            survived=1,
            mutation_score=0.9,
        ),
    )

    verdict = _judge().judge(evidence)

    assert verdict.status == "pass"
    assert verdict.explanation


def test_no_tests_is_warn():
    evidence = EvidenceBundle(
        target_file="x.py",
        module_name="x",
    )

    verdict = _judge().judge(evidence)

    assert verdict.status == "warn"
