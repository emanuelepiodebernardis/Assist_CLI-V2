"""Pipeline di verifica (Proof Engine v1).

Flusso:
  1. lettura + check sintassi (AST)
  2. analisi semantica (riusa SemanticAnalyzer esistente)
  3. run dei test esistenti in sandbox (se presenti)
  4. generazione test boundary con modello FAST
  5. run dei test boundary in sandbox
  6. mutation testing sui test disponibili
  7. verdetto: status deterministico + spiegazione/fix dal modello STRONG
"""

import ast
import re
from pathlib import Path

from assist.core.semantic_analyzer import SemanticAnalyzer
from assist.llm.base import LLMClient
from assist.schemas.models import SemanticAnalysis
from assist.verification.boundary_agent import BoundaryTestAgent
from assist.verification.dependency_collector import DependencyCollector
from assist.verification.evidence import (
    EvidenceBundle,
    MutationReport,
    TestRunEvidence,
    VerificationOutput,
)
from assist.verification.fix_loop import ValidatedFixLoop
from assist.verification.judge import EvidenceJudge
from assist.verification.mutation import MutationEngine
from assist.verification.pytest_report import parse_junit_xml
from assist.verification.sandbox import SandboxRunner
from assist.verification.test_discovery import TestDiscovery

_PYTEST_SUMMARY = re.compile(r"(\d+) (?:failed|error)", re.IGNORECASE)
_PYTEST_COLLECTED = re.compile(r"(\d+) (?:passed|failed|error)")


class VerificationPipeline:
    def __init__(
        self,
        fast_llm: LLMClient,
        strong_llm: LLMClient,
        sandbox_timeout: int = 30,
        mutation_threshold: float = 0.60,
        max_mutants: int = 40,
        generate_boundary_tests: bool = True,
        max_fix_iterations: int = 3,
        audience: str = "dev",
    ) -> None:
        self.sandbox = SandboxRunner(timeout_seconds=sandbox_timeout)
        self.boundary_agent = BoundaryTestAgent(llm=fast_llm)
        self.mutation_engine = MutationEngine(
            sandbox=self.sandbox,
            max_mutants=max_mutants,
        )
        self.judge = EvidenceJudge(
            llm=strong_llm,
            mutation_threshold=mutation_threshold,
            audience=audience,
        )
        self.fix_loop = ValidatedFixLoop(
            llm=strong_llm,
            sandbox=self.sandbox,
            max_iterations=max_fix_iterations,
        )
        self.generate_boundary_tests = generate_boundary_tests

    def run(
        self,
        file_path: str,
        tests_path: str | None = None,
        target_lines: set[int] | None = None,
    ) -> VerificationOutput:
        target = Path(file_path)
        source = target.read_text(encoding="utf-8")
        module_name = target.stem

        evidence = EvidenceBundle(
            target_file=str(target),
            module_name=module_name,
        )

        # 1. Sintassi
        try:
            ast.parse(source)
        except SyntaxError as exc:
            evidence.syntax_ok = False
            evidence.syntax_error = f"riga {exc.lineno}: {exc.msg}"
            verdict = self.judge.judge(evidence, source)
            return VerificationOutput(
                verdict=verdict,
                evidence=evidence,
                report_markdown=self._render_report(evidence, verdict),
            )

        # 2. Analisi semantica
        semantic: SemanticAnalysis | None = None
        try:
            semantic = SemanticAnalyzer().analyze_file(str(target))
        except Exception as exc:  # analisi best-effort
            evidence.notes.append(f"Analisi semantica saltata: {exc}")

        # 2b. Dipendenze locali (per sandbox multi-file)
        deps: dict[str, str] = {}
        try:
            deps = DependencyCollector().collect(str(target))
        except Exception as exc:
            evidence.notes.append(
                f"Raccolta dipendenze saltata: {exc}"
            )

        if deps:
            evidence.dependencies = sorted(deps)
            evidence.notes.append(
                f"Sandbox multi-file: incluse {len(deps)} dipendenze locali."
            )

        # 2c. Auto-discovery dei test se non indicati
        if tests_path is None:
            discovered = TestDiscovery().find_tests(str(target))
            if discovered:
                tests_path = discovered
                evidence.discovered_tests_path = discovered
                evidence.notes.append(
                    f"Test scoperti automaticamente: {discovered}"
                )

        # 3. Test esistenti
        existing_test_source = ""
        if tests_path:
            test_file = Path(tests_path)
            if test_file.exists():
                existing_test_source = test_file.read_text(encoding="utf-8")
                evidence.baseline_tests = self._run_tests(
                    source, module_name, existing_test_source,
                    "baseline", deps,
                )
            else:
                evidence.notes.append(
                    f"File di test indicato ma non trovato: {tests_path}"
                )

        # 4-5. Test boundary generati dal modello fast
        boundary_source = ""
        if self.generate_boundary_tests:
            boundary_source = self.boundary_agent.generate(
                source=source,
                module_name=module_name,
                semantic=semantic,
            )

            if boundary_source:
                evidence.boundary_tests_source = boundary_source
                evidence.boundary_tests = self._run_tests(
                    source, module_name, boundary_source,
                    "boundary", deps,
                )

                # Quarantena flaky: un fallimento va confermato da un
                # secondo run identico. Esiti diversi = test instabili,
                # esclusi dal verdetto e dal mutation testing.
                if not evidence.boundary_tests.passed:
                    rerun = self._run_tests(
                        source, module_name, boundary_source,
                        "boundary", deps,
                    )

                    if rerun.passed:
                        evidence.notes.append(
                            "Test boundary instabili (flaky): esito "
                            "diverso tra due run identici — messi in "
                            "quarantena, esclusi dal verdetto."
                        )
                        evidence.boundary_tests = None
                        boundary_source = ""
            else:
                evidence.notes.append(
                    "Generazione test boundary non riuscita "
                    "(output del modello non valido)."
                )

        # 6. Mutation testing (usa il test set piu' completo disponibile)
        mutation_test_source = "\n\n".join(
            src for src in (existing_test_source, boundary_source) if src
        )

        if mutation_test_source:
            evidence.mutation = self.mutation_engine.run(
                source=source,
                module_name=module_name,
                test_source=mutation_test_source,
                target_lines=target_lines,
                extra_files=deps,
            )
        else:
            evidence.mutation = MutationReport(
                skipped_reason="Nessun test disponibile."
            )

        # 7. Verdetto
        verdict = self.judge.judge(evidence, source)

        # 8. Fix loop validato: il fix e' accettato solo se i test
        #    rossi diventano verdi in sandbox.
        verdict = self._try_validated_fix(
            verdict=verdict,
            evidence=evidence,
            source=source,
            module_name=module_name,
            existing_test_source=existing_test_source,
            boundary_source=boundary_source,
            deps=deps,
        )

        return VerificationOutput(
            verdict=verdict,
            evidence=evidence,
            report_markdown=self._render_report(evidence, verdict),
        )

    def _try_validated_fix(
        self,
        verdict,
        evidence: EvidenceBundle,
        source: str,
        module_name: str,
        existing_test_source: str,
        boundary_source: str,
        deps: dict[str, str],
    ):
        """Se il verdetto e' fail per test rossi, tenta un fix e lo
        accetta solo dopo il pass dei test in sandbox."""

        if verdict.status != "fail":
            return verdict

        failing_source = ""
        failure_summary = ""

        if (
            evidence.baseline_tests is not None
            and not evidence.baseline_tests.passed
        ):
            failing_source = existing_test_source
            failure_summary = evidence.baseline_tests.failure_summary
        elif (
            evidence.boundary_tests is not None
            and not evidence.boundary_tests.passed
        ):
            failing_source = boundary_source
            failure_summary = evidence.boundary_tests.failure_summary

        if not failing_source:
            return verdict

        result = self.fix_loop.run(
            source=source,
            module_name=module_name,
            test_source=failing_source,
            failure_summary=failure_summary,
            extra_files=deps,
            initial_fix=verdict.proposed_fix,
        )

        if result.success:
            verdict.proposed_fix = result.validated_fix
            verdict.fix_validated = True
            verdict.reasons.append(
                "Fix validato in sandbox al tentativo "
                f"{result.iterations_used}: i test falliti ora passano."
            )
        else:
            evidence.notes.append(
                "Nessun fix validato entro "
                f"{self.fix_loop.max_iterations} tentativi."
            )

        return verdict

    def _run_tests(
        self,
        source: str,
        module_name: str,
        test_source: str,
        label: str,
        extra_files: dict[str, str] | None = None,
    ) -> TestRunEvidence:
        junit_out: list[str] = []

        result = self.sandbox.run_pytest(
            files={
                f"{module_name}.py": source,
                f"test_{label}_{module_name}.py": test_source,
                **(extra_files or {}),
            },
            collect_report=True,
            junit_xml_out=junit_out,
        )

        report = parse_junit_xml(junit_out[0] if junit_out else "")

        if report.parse_ok and report.total > 0:
            collected = report.total
            failed = report.failed + report.errors
            failure_summary = "\n".join(
                f"{case.classname}::{case.name}: {case.message}"
                for case in report.cases
                if case.outcome in ("failed", "error")
            )[:2000]
        else:
            # fallback: parsing a regex dell'output testuale
            output = result.stdout + "\n" + result.stderr

            failed = 0
            for match in _PYTEST_SUMMARY.finditer(output):
                failed += int(match.group(1))

            collected = sum(
                int(m.group(1))
                for m in _PYTEST_COLLECTED.finditer(output)
            )

            failure_summary = ""
            if not result.ok:
                failure_summary = _extract_failures(output)

        return TestRunEvidence(
            label=label,
            passed=result.ok,
            tests_collected=collected,
            tests_failed=failed,
            failure_summary=failure_summary,
            sandbox=result,
        )

    @staticmethod
    def _render_report(evidence, verdict) -> str:
        icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[verdict.status]

        lines = [
            f"# Verifica: {evidence.target_file}",
            "",
            f"**Verdetto: {icon}**",
            "",
            "## Evidenze",
            "",
        ]

        for reason in verdict.reasons:
            lines.append(f"- {reason}")

        if evidence.mutation and evidence.mutation.surviving_mutants:
            lines += ["", "## Mutanti sopravvissuti (test-bugia)", ""]
            for mr in evidence.mutation.surviving_mutants[:10]:
                lines.append(
                    f"- riga {mr.mutant.lineno}: {mr.mutant.description} "
                    f"— `{mr.mutant.original_snippet}`"
                )

        if verdict.explanation:
            lines += ["", "## Spiegazione", "", verdict.explanation]

        if verdict.proposed_fix:
            fix_title = (
                "## Fix validato in sandbox"
                if verdict.fix_validated
                else "## Fix proposto (non validato)"
            )
            lines += [
                "",
                fix_title,
                "",
                "```python",
                verdict.proposed_fix,
                "```",
            ]

        return "\n".join(lines)


def _extract_failures(output: str) -> str:
    """Estrae la sezione FAILURES/short summary dall'output pytest."""

    for marker in ("=========================== short test summary", "FAILURES"):
        idx = output.find(marker)
        if idx != -1:
            return output[idx : idx + 2000]

    return output[-2000:]
