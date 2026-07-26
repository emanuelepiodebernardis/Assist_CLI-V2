"""Ciclo di fix validato in sandbox (Validated Fix Loop) per TypeScript.

Speculare a `assist.verification.fix_loop.ValidatedFixLoop`, ma per
moduli TS/JS: un fix proposto dal modello forte non e' mai accettato
sulla parola. Ogni candidato viene estratto dal blocco di codice
restituito dal LLM ed eseguito nella sandbox Node (`TsSandboxRunner`)
contro i test vitest target. Non esiste un check di sintassi separato
(niente `ast.parse`, e' TypeScript): la validazione e' direttamente
l'esito del run vitest. Solo se i test passano davvero il fix e'
considerato "validato". Se il modello sbaglia, l'errore osservato
(messaggio dei test falliti o stderr, troncato) viene rimandato
indietro per un nuovo tentativo, fino a `max_iterations`.
"""

from __future__ import annotations

import re

from assist.llm.base import LLMClient
from assist.verification.evidence import SandboxResult, TestRunEvidence
from assist.verification.fix_loop import FixAttempt, FixLoopResult
from assist.verification.ts_runner import TsSandboxRunner, vitest_report_to_evidence

_CODE_BLOCK_RE = re.compile(
    r"```(?:ts|tsx|typescript|js|jsx|javascript)?\s*\n(.*?)```", re.DOTALL
)

_DETAIL_TRUNC_LEN = 1000

_SYSTEM = (
    "Sei un senior engineer TypeScript. Ricevi un file che non supera "
    "i test e il dettaglio del fallimento osservato in sandbox "
    "(vitest). Correggi il file in modo che tutti i test indicati "
    "passino. Rispondi con UN SOLO blocco ```typescript``` contenente "
    "il file completo e corretto, senza altro testo prima o dopo."
)

_PROMPT_TEMPLATE = """File: {module_file}

Sorgente attuale:
```typescript
{source}
```

Test che devono passare:
{test_files_block}

Errore osservato:
{failure_detail}

Correggi il sorgente del file affinche' i test sopra passino.
"""


class TsValidatedFixLoop:
    """Richiede fix TS/JS al modello forte e li accetta solo se
    superano i test vitest in sandbox, iterando fino a
    `max_iterations`."""

    def __init__(
        self,
        llm: LLMClient,
        runner: TsSandboxRunner | None = None,
        max_iterations: int = 3,
    ) -> None:
        self.llm = llm
        self.runner = runner or TsSandboxRunner()
        self.max_iterations = max_iterations

    def run(
        self,
        source: str,
        module_file: str,
        test_files: dict[str, str],
        failure_summary: str,
        extra_files: dict[str, str] | None = None,
        initial_fix: str = "",
    ) -> FixLoopResult:
        """Esegue il ciclo di fix e ritorna il primo candidato che
        supera i test vitest in sandbox, oppure un esito fallito dopo
        `max_iterations` tentativi."""

        files_extra = extra_files or {}
        attempts: list[FixAttempt] = []

        if initial_fix:
            candidate_raw = initial_fix
        else:
            candidate_raw = self._request_fix(
                source, module_file, test_files, failure_summary
            )

        for attempt_number in range(1, self.max_iterations + 1):
            code = self._extract_code(candidate_raw)

            if not code.strip():
                attempts.append(
                    FixAttempt(
                        attempt_number=attempt_number,
                        fix_source="",
                        tests_passed=False,
                        detail=(
                            "Nessun fix disponibile "
                            "(risposta LLM vuota)."
                        ),
                    )
                )
                break

            result, report = self.runner.run_vitest(
                files={
                    module_file: code,
                    **test_files,
                    **files_extra,
                },
            )

            evidence = vitest_report_to_evidence(
                report, result, label=f"ts-fix-{attempt_number}"
            )

            if evidence.passed:
                attempts.append(
                    FixAttempt(
                        attempt_number=attempt_number,
                        fix_source=code,
                        tests_passed=True,
                        detail="Test superati in sandbox (vitest).",
                    )
                )

                return FixLoopResult(
                    success=True,
                    validated_fix=code,
                    attempts=attempts,
                    iterations_used=attempt_number,
                )

            detail = self._render_failure_detail(evidence, result)
            attempts.append(
                FixAttempt(
                    attempt_number=attempt_number,
                    fix_source=code,
                    tests_passed=False,
                    detail=detail,
                )
            )

            if attempt_number == self.max_iterations:
                break

            candidate_raw = self._request_fix(
                source, module_file, test_files, detail
            )

        return FixLoopResult(
            success=False,
            validated_fix="",
            attempts=attempts,
            iterations_used=len(attempts),
        )

    def _request_fix(
        self,
        source: str,
        module_file: str,
        test_files: dict[str, str],
        failure_detail: str,
    ) -> str:
        """Chiede al LLM strong un nuovo file corretto, dato il
        dettaglio dell'ultimo fallimento osservato."""

        test_files_block = "\n\n".join(
            f"```typescript\n// {name}\n{content}\n```"
            for name, content in test_files.items()
        )

        prompt = _PROMPT_TEMPLATE.format(
            module_file=module_file,
            source=source,
            test_files_block=test_files_block,
            failure_detail=failure_detail or "Nessun dettaglio disponibile.",
        )

        return self.llm.complete(prompt=prompt, system=_SYSTEM)

    @staticmethod
    def _extract_code(text: str) -> str:
        """Estrae il codice da un blocco ```typescript``` (o varianti
        ts/js), come in `ValidatedFixLoop`. Se non c'e' nessun blocco,
        assume che il testo sia gia' codice puro."""

        match = _CODE_BLOCK_RE.search(text)
        if match:
            return match.group(1).strip()

        return text.strip()

    @staticmethod
    def _render_failure_detail(
        evidence: TestRunEvidence, result: SandboxResult
    ) -> str:
        """Rende il feedback per il LLM: il messaggio dei test
        falliti se presente, altrimenti stderr/stdout della sandbox,
        troncato a `_DETAIL_TRUNC_LEN` caratteri."""

        detail = evidence.failure_summary or result.stderr or result.stdout
        return detail[:_DETAIL_TRUNC_LEN]
