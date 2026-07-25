"""Esecuzione di test TypeScript (vitest) in una sandbox temporanea.

A differenza di `assist.verification.ts_support` (che delega a
StrykerJS per il mutation testing TS), questo modulo esegue i test
"normali" scritti con vitest, sul modello di
`assist.verification.sandbox.SandboxRunner` ma per progetti Node.

Il progetto non installa Node/vitest: si appoggia a un "template"
gia' pronto (una directory con `node_modules` e `package.json` che
contengono almeno vitest, fast-check e typescript) individuato da
`ts_template_dir`. Ogni run crea una directory temporanea, vi
sym-linka `node_modules` dal template (evita di reinstallare le
dipendenze npm a ogni esecuzione), copia il `package.json` del
template, scrive i file forniti dal chiamante ed esegue
``npx vitest run --reporter=json``, il cui stdout viene parsato come
report JSON strutturato.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from assist.verification.evidence import SandboxResult, TestRunEvidence

DEFAULT_TS_TIMEOUT_SECONDS = 60

# Directory di default in cui cercare il template TS (sovrascrivibile
# con la variabile d'ambiente ASSIST_TS_TEMPLATE).
DEFAULT_TEMPLATE_DIR = Path.home() / ".assist" / "ts-template"

# Fallback usato quando ne' l'env var ne' il default contengono un
# template valido. Esposto come costante di modulo (non hardcoded
# dentro la funzione) cosi' i test possono sovrascriverlo con
# `monkeypatch.setattr(ts_runner, "FALLBACK_TEMPLATE_DIR", ...)`.
FALLBACK_TEMPLATE_DIR = Path("/tmp/ts_template")

_MAX_FAILURE_SUMMARY_LEN = 2000
_MAX_OUTPUT_LEN = 20000

# Sentinella per distinguere "cache non ancora calcolata" da "cache
# calcolata e il risultato e' None" (nessun template trovato).
_UNSET = object()
_cached_template_dir: object = _UNSET


def _has_vitest(directory: Path) -> bool:
    """Ritorna True se `directory` contiene un vitest installato."""

    return (directory / "node_modules" / ".bin" / "vitest").exists()


def ts_template_dir() -> Path | None:
    """Individua la directory del template Node/vitest da usare.

    Legge la variabile d'ambiente ``ASSIST_TS_TEMPLATE`` (default
    `DEFAULT_TEMPLATE_DIR`, ovvero ``~/.assist/ts-template``): se la
    directory risolta non contiene ``node_modules/.bin/vitest``,
    prova il fallback `FALLBACK_TEMPLATE_DIR`. Se nemmeno questo e'
    valido ritorna None.

    Il risultato e' cachato a livello di modulo: vedi
    `reset_ts_template_dir_cache` per azzerare la cache nei test.
    """

    global _cached_template_dir

    if _cached_template_dir is not _UNSET:
        return _cached_template_dir  # type: ignore[return-value]

    env_value = os.environ.get("ASSIST_TS_TEMPLATE", "")
    primary = Path(env_value).expanduser() if env_value else DEFAULT_TEMPLATE_DIR

    if _has_vitest(primary):
        _cached_template_dir = primary
    elif _has_vitest(FALLBACK_TEMPLATE_DIR):
        _cached_template_dir = FALLBACK_TEMPLATE_DIR
    else:
        _cached_template_dir = None

    return _cached_template_dir  # type: ignore[return-value]


def reset_ts_template_dir_cache() -> None:
    """Azzera la cache di modulo di `ts_template_dir` (solo test)."""

    global _cached_template_dir
    _cached_template_dir = _UNSET


def ts_available() -> bool:
    """Ritorna True se `node` e' nel PATH e un template TS e' trovato."""

    return shutil.which("node") is not None and ts_template_dir() is not None


def _extract_json_report(stdout: str) -> dict:
    """Estrae il primo blocco JSON valido dallo stdout di vitest.

    Vitest con ``--reporter=json`` scrive normalmente il report come
    unico oggetto JSON su stdout, ma puo' precedere output extra
    (warning, log di npx, ecc.): si cerca ogni occorrenza di ``{`` e
    si tenta un "raw decode" da quel punto, ignorando eventuale
    contenuto dopo la chiusura dell'oggetto. Ritorna `{}` se nessun
    blocco e' parsabile.
    """

    decoder = json.JSONDecoder()
    idx = stdout.find("{")

    while idx != -1:
        try:
            obj, _end = decoder.raw_decode(stdout, idx)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        idx = stdout.find("{", idx + 1)

    return {}


class TsSandboxRunner:
    """Esegue test vitest in una sandbox Node temporanea usa-e-getta."""

    def __init__(self, timeout_seconds: int = DEFAULT_TS_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        self.runs = 0  # contatore esecuzioni (telemetria)

    def run_vitest(self, files: dict[str, str]) -> tuple[SandboxResult, dict]:
        """Scrive `files` in una dir temporanea ed esegue vitest.

        Ritorna una tupla `(SandboxResult, report)`: `report` e' il
        dict del JSON prodotto da vitest (`{}` se il template non e'
        disponibile o il parsing fallisce). Nessuna eccezione viene
        propagata al chiamante: assenza del template, symlink fallito
        o timeout producono un `SandboxResult` con `exit_code` non
        zero e uno `stderr` esplicativo.
        """

        template = ts_template_dir()

        if template is None:
            return (
                SandboxResult(
                    exit_code=-1,
                    stderr=(
                        "Template TypeScript non trovato: imposta la "
                        "variabile d'ambiente ASSIST_TS_TEMPLATE oppure "
                        f"installa il template in '{FALLBACK_TEMPLATE_DIR}' "
                        f"(o in '{DEFAULT_TEMPLATE_DIR}')."
                    ),
                    timed_out=False,
                ),
                {},
            )

        workdir = Path(tempfile.mkdtemp(prefix="assist_ts_sandbox_"))

        try:
            try:
                os.symlink(
                    template / "node_modules",
                    workdir / "node_modules",
                    target_is_directory=True,
                )
            except OSError as exc:
                return (
                    SandboxResult(
                        exit_code=-1,
                        stderr=(
                            "Impossibile creare il symlink verso "
                            f"'node_modules' del template: {exc}"
                        ),
                        timed_out=False,
                    ),
                    {},
                )

            template_package_json = template / "package.json"
            if template_package_json.exists():
                shutil.copy2(template_package_json, workdir / "package.json")

            for name, content in files.items():
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            return self._run_vitest(workdir)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _run_vitest(self, workdir: Path) -> tuple[SandboxResult, dict]:
        """Lancia `npx vitest run --reporter=json` in `workdir`."""

        self.runs += 1
        start = time.monotonic()
        cmd = ["npx", "vitest", "run", "--reporter=json"]

        try:
            completed = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env={"PATH": os.environ.get("PATH", "")},
            )
            duration = time.monotonic() - start
            report = _extract_json_report(completed.stdout)
            success = bool(report.get("success")) if report else False

            result = SandboxResult(
                exit_code=0 if success else 1,
                stdout=completed.stdout[-_MAX_OUTPUT_LEN:],
                stderr=completed.stderr[-_MAX_OUTPUT_LEN:],
                duration_seconds=round(duration, 3),
                timed_out=False,
            )
            return result, report

        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            result = SandboxResult(
                exit_code=-1,
                stdout=stdout[-_MAX_OUTPUT_LEN:],
                stderr=stderr[-_MAX_OUTPUT_LEN:],
                duration_seconds=round(duration, 3),
                timed_out=True,
            )
            return result, {}

        except OSError as exc:
            duration = time.monotonic() - start
            result = SandboxResult(
                exit_code=-1,
                stderr=f"Esecuzione di 'npx vitest' fallita: {exc}",
                duration_seconds=round(duration, 3),
                timed_out=False,
            )
            return result, {}


def vitest_report_to_evidence(
    report: dict,
    result: SandboxResult,
    label: str,
) -> TestRunEvidence:
    """Converte un report JSON di vitest in un `TestRunEvidence`.

    `tests_collected`/`tests_failed` vengono letti da
    ``numTotalTests``/``numFailedTests``; `passed` e' vero solo se
    ``success`` e' vero nel report e la sandbox non e' andata in
    timeout. `failure_summary` concatena i messaggi di errore dei
    test falliti: il campo ``message`` di ogni `testResults` (usato
    da vitest per errori a livello di suite, es. di sintassi) e le
    ``failureMessages`` di ogni `assertionResults` con esito
    "failed" (usate per le singole asserzioni fallite), troncata a
    2000 caratteri complessivi.
    """

    tests_collected = int(report.get("numTotalTests", 0) or 0)
    tests_failed = int(report.get("numFailedTests", 0) or 0)
    success = bool(report.get("success", False))
    passed = success and not result.timed_out

    summary_parts: list[str] = []

    for test_result in report.get("testResults", []) or []:
        message = test_result.get("message") or ""
        if message:
            summary_parts.append(message)

        for assertion in test_result.get("assertionResults", []) or []:
            if assertion.get("status") != "failed":
                continue
            for failure_message in assertion.get("failureMessages", []) or []:
                summary_parts.append(failure_message)

    failure_summary = "\n".join(summary_parts)[:_MAX_FAILURE_SUMMARY_LEN]

    return TestRunEvidence(
        label=label,
        passed=passed,
        tests_collected=tests_collected,
        tests_failed=tests_failed,
        failure_summary=failure_summary,
        sandbox=result,
    )
