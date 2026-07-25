"""Ciclo di fix validato in sandbox (Validated Fix Loop).

Principio: un fix proposto dal modello forte non e' mai accettato
sulla parola. Ogni candidato viene estratto, controllato
sintatticamente e poi eseguito nella sandbox contro il test target.
Solo se i test passano davvero il fix e' considerato "validato".
Se il modello sbaglia, l'errore osservato viene rimandato indietro
per un nuovo tentativo, fino a `max_iterations`.
"""

import ast
import re

from pydantic import BaseModel, Field

from assist.llm.base import LLMClient
from assist.verification.evidence import SandboxResult
from assist.verification.sandbox import SandboxRunner

_CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

_DETAIL_TRUNC_LEN = 1000

_SYSTEM = (
    "Sei un senior engineer. Ricevi un file Python che non supera i "
    "test e il dettaglio del fallimento osservato. Correggi il file "
    "in modo che tutti i test indicati passino. Rispondi con UN SOLO "
    "blocco ```python``` contenente il file completo e corretto, "
    "senza altro testo prima o dopo."
)

_PROMPT_TEMPLATE = """Modulo: {module_name}.py

Sorgente attuale:
```python
{source}
```

Test che deve passare:
```python
{test_source}
```

Errore osservato:
{failure_detail}

Correggi il sorgente del modulo affinche' il test sopra passi.
"""


class FixAttempt(BaseModel):
    """Un singolo tentativo di fix con il relativo esito in sandbox."""

    attempt_number: int
    fix_source: str
    tests_passed: bool
    detail: str = ""


class FixLoopResult(BaseModel):
    """Esito del ciclo di fix validato in sandbox."""

    success: bool
    validated_fix: str = ""
    attempts: list[FixAttempt] = Field(default_factory=list)
    iterations_used: int = 0


class ValidatedFixLoop:
    """Richiede fix al modello forte e li accetta solo se superano
    i test in sandbox, iterando fino a `max_iterations`."""

    def __init__(
        self,
        llm: LLMClient,
        sandbox: SandboxRunner | None = None,
        max_iterations: int = 3,
    ) -> None:
        self.llm = llm
        self.sandbox = sandbox or SandboxRunner()
        self.max_iterations = max_iterations

    def run(
        self,
        source: str,
        module_name: str,
        test_source: str,
        failure_summary: str,
        extra_files: dict[str, str] | None = None,
        initial_fix: str = "",
    ) -> FixLoopResult:
        """Esegue il ciclo di fix e ritorna il primo candidato che
        supera i test in sandbox, oppure un esito fallito dopo
        `max_iterations` tentativi."""

        files_extra = extra_files or {}
        attempts: list[FixAttempt] = []

        if initial_fix:
            candidate_raw = initial_fix
        else:
            candidate_raw = self._request_fix(
                source, module_name, test_source, failure_summary
            )

        for attempt_number in range(1, self.max_iterations + 1):
            code = self._extract_code(candidate_raw)

            syntax_error = self._check_syntax(code)
            if syntax_error:
                attempts.append(
                    FixAttempt(
                        attempt_number=attempt_number,
                        fix_source=code,
                        tests_passed=False,
                        detail=syntax_error,
                    )
                )

                if attempt_number == self.max_iterations:
                    break

                candidate_raw = self._request_fix(
                    source, module_name, test_source, syntax_error
                )
                continue

            result = self.sandbox.run_pytest(
                files={
                    f"{module_name}.py": code,
                    "test_target.py": test_source,
                    **files_extra,
                },
            )

            if result.ok:
                attempts.append(
                    FixAttempt(
                        attempt_number=attempt_number,
                        fix_source=code,
                        tests_passed=True,
                        detail="Test superati in sandbox.",
                    )
                )

                return FixLoopResult(
                    success=True,
                    validated_fix=code,
                    attempts=attempts,
                    iterations_used=attempt_number,
                )

            detail = self._render_sandbox_detail(result)
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
                source, module_name, test_source, detail
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
        module_name: str,
        test_source: str,
        failure_detail: str,
    ) -> str:
        """Chiede al LLM strong un nuovo file corretto, dato il
        dettaglio dell'ultimo fallimento osservato."""

        prompt = _PROMPT_TEMPLATE.format(
            module_name=module_name,
            source=source,
            test_source=test_source,
            failure_detail=failure_detail or "Nessun dettaglio disponibile.",
        )

        return self.llm.complete(prompt=prompt, system=_SYSTEM)

    @staticmethod
    def _extract_code(text: str) -> str:
        """Estrae il codice da un blocco ```python```, come in
        judge.py. Se non c'e' nessun blocco, assume che il testo
        sia gia' codice puro."""

        match = _CODE_BLOCK_RE.search(text)
        if match:
            return match.group(1).strip()

        return text.strip()

    @staticmethod
    def _check_syntax(code: str) -> str:
        """Ritorna una stringa di errore se `code` non e' Python
        valido, altrimenti stringa vuota."""

        try:
            ast.parse(code)
        except SyntaxError as exc:
            return f"Errore di sintassi nel fix proposto: riga {exc.lineno}: {exc.msg}"

        return ""

    @staticmethod
    def _render_sandbox_detail(result: SandboxResult) -> str:
        """Rende stdout/stderr della sandbox troncati per il feedback
        al LLM."""

        stdout = result.stdout[-_DETAIL_TRUNC_LEN:]
        stderr = result.stderr[-_DETAIL_TRUNC_LEN:]

        return f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
