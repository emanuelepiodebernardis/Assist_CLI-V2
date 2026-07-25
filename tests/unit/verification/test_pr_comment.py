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


def _warn_output_with_unvalidated_fix() -> VerificationOutput:
    """Output finto per un file "warn" con un fix proposto ma non validato."""
    evidence = EvidenceBundle(
        target_file="src/warn.py",
        module_name="warn",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=True,
            tests_collected=1,
            tests_failed=0,
            sandbox=_sandbox_ok(),
        ),
    )

    verdict = Verdict(
        status="warn",
        reasons=["Mutation score sotto la soglia consigliata."],
        explanation="Copertura parziale.",
        proposed_fix="def warn():\n    return None\n",
        fix_validated=False,
        mutation_score=0.5,
    )

    return VerificationOutput(verdict=verdict, evidence=evidence)


def test_fix_column_shows_three_states() -> None:
    outputs = [
        ("src/ok.py", _pass_output()),
        ("src/warn.py", _warn_output_with_unvalidated_fix()),
        ("src/bad.py", _fail_output()),
    ]

    comment = render_pr_comment(outputs)

    row_ok = next(
        line for line in comment.splitlines() if line.startswith("| `src/ok.py`")
    )
    row_warn = next(
        line for line in comment.splitlines() if line.startswith("| `src/warn.py`")
    )
    row_bad = next(
        line for line in comment.splitlines() if line.startswith("| `src/bad.py`")
    )

    assert row_ok.rstrip().endswith("| — |")
    assert row_warn.rstrip().endswith("| proposto |")
    assert row_bad.rstrip().endswith("| ✅ validato |")


def test_nested_sandbox_log_and_mutant_detail_sections() -> None:
    """Le due sotto-sezioni annidate devono comparire coi dati grezzi."""
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
            detail="Nessun test verifica il caso limite a == b.",
        ),
    ]

    evidence = EvidenceBundle(
        target_file="src/bad.py",
        module_name="bad",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_collected=2,
            tests_failed=1,
            failure_summary="AssertionError: expected 1, got 0",
            sandbox=SandboxResult(exit_code=1, stdout="riga1\nriga2"),
        ),
        boundary_tests=TestRunEvidence(
            label="boundary",
            passed=False,
            tests_collected=1,
            tests_failed=1,
            sandbox=SandboxResult(
                exit_code=1,
                stdout="riga_boundary_1\nriga_boundary_2",
                stderr="err1",
            ),
        ),
        mutation=MutationReport(
            total_mutants=5,
            killed=4,
            survived=1,
            mutation_score=0.8,
            surviving_mutants=surviving,
        ),
    )

    verdict = Verdict(
        status="fail",
        reasons=["motivo di fallimento"],
        mutation_score=0.8,
    )

    output = VerificationOutput(verdict=verdict, evidence=evidence)

    comment = render_pr_comment([("src/bad.py", output)])

    assert "📋 Log di esecuzione (sandbox)" in comment
    assert "**baseline** — ❌ fallito" in comment
    assert "AssertionError: expected 1, got 0" in comment
    assert "**boundary** — ❌ fallito" in comment
    # boundary non ha failure_summary -> si usa la coda di stdout+stderr.
    assert "riga_boundary_1" in comment
    assert "err1" in comment

    assert "🧬 Dettaglio mutanti sopravvissuti" in comment
    assert "| Riga | Mutazione | Codice originale | Perché conta |" in comment
    assert "Nessun test verifica il caso limite a == b." in comment


def test_mutant_detail_table_caps_rows_and_counts_remaining() -> None:
    surviving = [
        MutantResult(
            mutant=Mutant(
                mutant_id=i,
                lineno=i,
                description=f"desc {i}",
                original_snippet=f"x{i}",
            ),
            killed=False,
        )
        for i in range(1, 31)
    ]

    evidence = EvidenceBundle(
        target_file="src/many.py",
        module_name="many",
        mutation=MutationReport(
            total_mutants=40,
            killed=10,
            survived=30,
            mutation_score=0.25,
            surviving_mutants=surviving,
        ),
    )

    verdict = Verdict(
        status="fail",
        reasons=["troppi mutanti sopravvissuti"],
        mutation_score=0.25,
    )

    output = VerificationOutput(verdict=verdict, evidence=evidence)

    comment = render_pr_comment([("src/many.py", output)])

    assert "desc 1 " in comment or "desc 1 |" in comment
    assert "desc 25" in comment
    assert "desc 26" not in comment
    assert "... e altri 5" in comment


def test_truncation_sacrifices_sandbox_logs_before_base_sections() -> None:
    outputs = []

    for i in range(40):
        path = f"src/file_{i}.py"
        surviving = [
            MutantResult(
                mutant=Mutant(
                    mutant_id=i,
                    lineno=1,
                    description="mutazione",
                    original_snippet="a",
                ),
                killed=False,
                detail="motivo",
            )
        ]
        evidence = EvidenceBundle(
            target_file=path,
            module_name=f"file_{i}",
            baseline_tests=TestRunEvidence(
                label="baseline",
                passed=False,
                tests_collected=1,
                tests_failed=1,
                sandbox=SandboxResult(
                    exit_code=1,
                    stdout="log " * 500,
                    stderr="err " * 500,
                ),
            ),
            mutation=MutationReport(
                total_mutants=2,
                killed=1,
                survived=1,
                mutation_score=0.5,
                surviving_mutants=surviving,
            ),
        )
        verdict = Verdict(
            status="fail",
            reasons=[f"motivo {i}"],
            mutation_score=0.5,
        )
        outputs.append((path, VerificationOutput(verdict=verdict, evidence=evidence)))

    comment = render_pr_comment(outputs)

    assert len(comment) < 65536
    assert "(output troncato)" in comment
    assert "## 🔬 Assist Proof Engine" in comment
    assert "| File | Verdetto | Mutation score | Test | Fix |" in comment
    for path, _ in outputs:
        assert f"`{path}`" in comment

    assert "motivo 0" in comment
    assert "📋 Log di esecuzione (sandbox)" not in comment
    assert "🧬 Dettaglio mutanti sopravvissuti" in comment


def test_truncation_sacrifices_mutant_detail_after_logs() -> None:
    outputs = []

    for i in range(40):
        path = f"src/many_{i}.py"
        surviving = [
            MutantResult(
                mutant=Mutant(
                    mutant_id=j,
                    lineno=j,
                    description=f"mutazione numero {j}",
                    original_snippet=f"codice_originale_{j}",
                ),
                killed=False,
                detail=(f"dettaglio molto lungo per il mutante numero {j} " * 2),
            )
            for j in range(1, 15)
        ]
        evidence = EvidenceBundle(
            target_file=path,
            module_name=f"many_{i}",
            mutation=MutationReport(
                total_mutants=20,
                killed=6,
                survived=14,
                mutation_score=0.3,
                surviving_mutants=surviving,
            ),
        )
        verdict = Verdict(
            status="fail",
            reasons=[f"motivo {i}"],
            mutation_score=0.3,
        )
        outputs.append((path, VerificationOutput(verdict=verdict, evidence=evidence)))

    comment = render_pr_comment(outputs)

    assert len(comment) < 65536
    assert "(output troncato)" in comment
    assert "## 🔬 Assist Proof Engine" in comment
    assert "| File | Verdetto | Mutation score | Test | Fix |" in comment
    assert "motivo 0" in comment
    assert "🧬 Dettaglio mutanti sopravvissuti" not in comment
    assert "📋 Log di esecuzione (sandbox)" not in comment


def test_sandbox_log_truncated_to_1500_chars_per_run() -> None:
    """Il blocco di log per singolo run non supera i 1500 caratteri."""
    evidence = EvidenceBundle(
        target_file="src/bad.py",
        module_name="bad",
        baseline_tests=TestRunEvidence(
            label="baseline",
            passed=False,
            tests_collected=1,
            tests_failed=1,
            sandbox=SandboxResult(exit_code=1, stdout="Y" * 3000),
        ),
    )

    verdict = Verdict(status="fail", reasons=["motivo"])
    output = VerificationOutput(verdict=verdict, evidence=evidence)

    comment = render_pr_comment([("src/bad.py", output)])

    assert "📋 Log di esecuzione (sandbox)" in comment
    assert "Y" * 3000 not in comment
    assert "Y" * 1500 in comment
