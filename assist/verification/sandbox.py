"""Esecuzione isolata di codice e test in sandbox.

Ogni run avviene in una directory temporanea usa-e-getta, in un
sottoprocesso Python separato con timeout. Nessuno stato condiviso
con il processo principale.

Nota: isolamento a livello di processo (sufficiente per codice
proprio/di fiducia in locale). La roadmap prevede container/gVisor
per codice arbitrario lato SaaS (Fase 3).
"""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from assist.verification.evidence import SandboxResult

DEFAULT_TIMEOUT_SECONDS = 30


class SandboxRunner:
    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.runs = 0  # contatore esecuzioni (telemetria)

    def run_pytest(
        self,
        files: dict[str, str],
        extra_args: list[str] | None = None,
        collect_report: bool = False,
        junit_xml_out: list[str] | None = None,
    ) -> SandboxResult:
        """Scrive `files` (nome -> contenuto) in una dir temporanea
        e vi esegue pytest. Ritorna l'esito grezzo.

        Parametri opzionali per il parsing strutturato via JUnit XML
        (vedi `assist.verification.pytest_report.parse_junit_xml`):

        - `collect_report`: se True, aggiunge agli argomenti di pytest
          `--junit-xml=<workdir>/_assist_junit.xml`, cosi' pytest scrive
          il report XML nella dir temporanea insieme ai file di test.
        - `junit_xml_out`: lista mutabile fornita dal chiamante in cui
          viene appesa (side-effect) una singola stringa col contenuto
          del report XML letto, oppure stringa vuota se il file non
          esiste (es. pytest crashato prima di scriverlo). Serve perche'
          la dir temporanea viene CANCELLATA nel blocco `finally` prima
          che il valore di ritorno raggiunga il chiamante, e
          `SandboxResult` (in evidence.py) non ha un campo dedicato al
          report XML: la lettura del file deve quindi avvenire qui,
          dentro `run_pytest`, subito prima della pulizia, e il
          contenuto va restituito tramite questo parametro "out" invece
          che tramite il valore di ritorno.

        La firma resta retrocompatibile: chiamando `run_pytest` senza i
        nuovi parametri il comportamento e' identico a prima.
        """

        args = extra_args or ["-q", "--no-header", "-p", "no:cacheprovider"]

        workdir = Path(tempfile.mkdtemp(prefix="assist_sandbox_"))
        junit_path = workdir / "_assist_junit.xml"

        if collect_report:
            args = [*args, f"--junit-xml={junit_path}"]

        try:
            for name, content in files.items():
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            return self._run(
                [sys.executable, "-m", "pytest", *args],
                cwd=workdir,
            )
        finally:
            if collect_report and junit_xml_out is not None:
                if junit_path.exists():
                    junit_xml_out.append(junit_path.read_text(encoding="utf-8"))
                else:
                    junit_xml_out.append("")
            shutil.rmtree(workdir, ignore_errors=True)

    def run_script(
        self,
        files: dict[str, str],
        entry: str,
    ) -> SandboxResult:
        """Esegue un singolo script Python nella sandbox."""

        workdir = Path(tempfile.mkdtemp(prefix="assist_sandbox_"))

        try:
            for name, content in files.items():
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            return self._run(
                [sys.executable, entry],
                cwd=workdir,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _run(
        self,
        cmd: list[str],
        cwd: Path,
    ) -> SandboxResult:
        self.runs += 1
        start = time.monotonic()

        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env={
                    "PATH": _safe_path(),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
            )
            duration = time.monotonic() - start

            return SandboxResult(
                exit_code=completed.returncode,
                stdout=completed.stdout[-20000:],
                stderr=completed.stderr[-20000:],
                duration_seconds=round(duration, 3),
                timed_out=False,
            )

        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""

            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            return SandboxResult(
                exit_code=-1,
                stdout=stdout[-20000:],
                stderr=stderr[-20000:],
                duration_seconds=round(duration, 3),
                timed_out=True,
            )


def _safe_path() -> str:
    import os

    return os.environ.get("PATH", "")
