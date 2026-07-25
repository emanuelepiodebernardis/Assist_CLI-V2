"""Test per il rendering del commento PR (assist.verification.pr_comment)."""

from assist.verification.evidence import (
    EvidenceBundle,
    Mutant,
    MutantResult,
    MutationReport,
    SandboxResult,
    TestRunEvidence,
    Verdict,
    VerificationOutput,
)
from assist.verification.pr_comment import render_pr_comment


def _sandbox_ok() -> SandboxResult:
    return SandboxResult(exit_code=0)


def _pass_output() -> VerificationOutput:
    """Output finto per un file che passa con mutation score alto."""
    evidence = EvidenceBundle(
        target_file="src/ok.py",
        module_name="ok",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=True,
            tests_collected=3,
            tests_failed=0,
            sandbox=_sandbox_ok(),
        ),
        mutation=MutationReport(
            total_mutants=10,
            killed=9,
            survived=1,
            mutation_score=0.9,
        ),
    )

    verdict = Verdict(
        status="pass",
        reasons=["Tutti i test eseguiti passano in sandbox."],
        explanation="Il codice e' coperto adeguatamente.",
        mutation_score=0.9,
    )

    return VerificationOutput(verdict=verdict, evidence=evidence)


def _fail_output() -> VerificationOutput:
    """Output finto per un file che fallisce, con mutanti e fix validato."""
    surviving = [
        MutantResult(
            mutant=Mutant(
                mutant_id=1,
                lineno=12,
                description="Comparatore invertito",
                original_snippet="a < b",
                mutated_snippet="a > b",
            ),
            killed=False,
        ),
        MutantResult(
            mutant=Mutant(
                mutant_id=2,
                lineno=27,
                description="Costante numerica alterata",
                original_snippet="return 0",
                mutated_snippet="return 1",
            ),
            killed=False,
        ),
    ]

    evidence = EvidenceBundle(
        target_file="src/bad.py",
        module_name="bad",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_collected=2,
            tests_failed=2,
            sandbox=SandboxResult(exit_code=1),
        ),
        mutation=MutationReport(
            total_mutants=10,
            killed=8,
            survived=2,
            mutation_score=0.8,
            surviving_mutants=surviving,
        ),
    )

    verdict = Verdict(
        status="fail",
        reasons=[
            "I test esistenti falliscono in sandbox (2 falliti).",
            "Mutation score 80% sotto la soglia richiesta.",
        ],
        explanation="I test rossi indicano un comportamento errato.",
        proposed_fix="def bad():\n    return True\n",
        fix_validated=True,
        mutation_score=0.8,
    )

    return VerificationOutput(verdict=verdict, evidence=evidence)


def test_header_and_summary_counts() -> None:
    outputs = [("src/ok.py", _pass_output()), ("src/bad.py", _fail_output())]

    comment = render_pr_comment(outputs)

    assert "## 🔬 Assist Proof Engine" in comment
    assert "2 file verificati" in comment
    assert "✅ 1 pass" in comment
    assert "⚠️ 0 warn" in comment
    assert "❌ 1 fail" in comment


def test_table_has_one_row_per_file() -> None:
    outputs = [("src/ok.py", _pass_output()), ("src/bad.py", _fail_output())]

    comment = render_pr_comment(outputs)

    assert "| File | Verdetto | Mutation score | Test |" in comment
    assert "`src/ok.py`" in comment
    assert "`src/bad.py`" in comment
    assert "90%" in comment
    assert "80%" in comment
    assert "3 ok" in comment
    assert "2 falliti" in comment


def test_details_only_for_non_pass_files() -> None:
    outputs = [("src/ok.py", _pass_output()), ("src/bad.py", _fail_output())]

    comment = render_pr_comment(outputs)

    # Il file "pass" non deve avere una sezione <details> dedicata.
    assert "<code>src/ok.py</code>" not in comment
    assert "<code>src/bad.py</code>" in comment
    assert "<details>" in comment
    assert "</details>" in comment


def test_fail_section_includes_reasons_mutants_and_validated_fix() -> None:
    outputs = [("src/bad.py", _fail_output())]

    comment = render_pr_comment(outputs)

    assert "I test esistenti falliscono in sandbox (2 falliti)." in comment
    assert "Mutation score 80% sotto la soglia richiesta." in comment

    assert "riga 12" in comment
    assert "Comparatore invertito" in comment
    assert "`a < b`" in comment
    assert "riga 27" in comment
    assert "Costante numerica alterata" in comment

    assert "validato" in comment
    assert "```python" in comment
    assert "def bad():" in comment


def test_footer_present() -> None:
    outputs = [("src/ok.py", _pass_output())]

    comment = render_pr_comment(outputs)

    assert "Generato da Assist CLI" in comment


def test_truncation_keeps_header_and_table_within_limit() -> None:
    huge_fix = "x = 1\n" * 20_000  # ~120.000 caratteri

    evidence = EvidenceBundle(
        target_file="src/huge.py",
        module_name="huge",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_collected=1,
            tests_failed=1,
            sandbox=SandboxResult(exit_code=1),
        ),
    )

    verdict = Verdict(
        status="fail",
        reasons=["I test esistenti falliscono in sandbox (1 falliti)."],
        explanation="Fix enorme di prova.",
        proposed_fix=huge_fix,
        fix_validated=True,
    )

    output = VerificationOutput(verdict=verdict, evidence=evidence)

    comment = render_pr_comment([("src/huge.py", output)])

    assert len(comment) < 65536
    assert "(output troncato)" in comment
    assert "## 🔬 Assist Proof Engine" in comment
    assert "| File | Verdetto | Mutation score | Test |" in comment
    assert "`src/huge.py`" in comment
