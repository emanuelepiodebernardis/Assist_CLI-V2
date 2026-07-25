"""Esecuzione isolata di codice e test in sandbox Docker.

Alternativa a `SandboxRunner` (isolamento di processo) per chi vuole
un isolamento piu' forte (nessun accesso di rete, limiti di memoria e
CPU) sfruttando un container Docker usa-e-getta. L'interfaccia
pubblica ricalca quella di `SandboxRunner` cosi' le due classi sono
intercambiabili (vedi `make_sandbox`).

Nota: se Docker non e' disponibile nell'ambiente, `make_sandbox`
esegue automaticamente il fallback a `SandboxRunner`.
"""

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from assist.verification.evidence import SandboxResult
from assist.verification.sandbox import SandboxRunner

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_IMAGE = "python:3.11-slim"
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPUS = "1.0"
CONTAINER_STARTUP_GRACE_SECONDS = 30
JUNIT_XML_FILENAME = "_assist_junit.xml"

logger = logging.getLogger(__name__)

_docker_available_cache: bool | None = None


def docker_available() -> bool:
    """Verifica se Docker e' disponibile eseguendo `docker info`.

    Il risultato viene cachato a livello di modulo (una sola chiamata
    per processo); usare `reset_docker_cache()` nei test per forzare
    una nuova verifica.
    """

    global _docker_available_cache

    if _docker_available_cache is not None:
        return _docker_available_cache

    try:
        completed = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        _docker_available_cache = completed.returncode == 0
    except Exception:
        _docker_available_cache = False

    return _docker_available_cache


def reset_docker_cache() -> None:
    """Azzera la cache di `docker_available()` (usato nei test)."""

    global _docker_available_cache
    _docker_available_cache = None


class DockerSandboxRunner:
    """Esegue pytest/script Python isolati in un container Docker.

    Stessa interfaccia pubblica di `SandboxRunner` (run_pytest,
    run_script, attributi `runs` e `timeout_seconds`) cosi' da poter
    essere usata come sostituto drop-in.
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        image: str = DEFAULT_IMAGE,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpus: str = DEFAULT_CPUS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.image = image
        self.memory_limit = memory_limit
        self.cpus = cpus
        self.runs = 0  # contatore esecuzioni (telemetria)

    def run_pytest(
        self,
        files: dict[str, str],
        extra_args: list[str] | None = None,
        collect_report: bool = False,
        junit_xml_out: list[str] | None = None,
    ) -> SandboxResult:
        """Scrive `files` in una dir temporanea e vi esegue pytest
        dentro un container Docker usa-e-getta.

        Semantica di `collect_report`/`junit_xml_out` identica a
        `SandboxRunner.run_pytest`: se `collect_report` e' True viene
        aggiunto `--junit-xml=...` e il contenuto del report XML
        prodotto viene appeso (side-effect) a `junit_xml_out`.
        """

        args = extra_args or ["-q", "--no-header", "-p", "no:cacheprovider"]

        workdir = Path(tempfile.mkdtemp(prefix="assist_docker_sandbox_"))
        outdir = Path(tempfile.mkdtemp(prefix="assist_docker_sandbox_out_"))
        junit_path = outdir / JUNIT_XML_FILENAME

        pytest_cmd = "python -m pytest " + " ".join(args)
        if collect_report:
            pytest_cmd = f"{pytest_cmd} --junit-xml=/out/{JUNIT_XML_FILENAME}"

        shell_cmd = f"cp -r /work/* /tmp/ && {pytest_cmd}"

        try:
            for name, content in files.items():
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            cmd = self._docker_cmd(workdir, outdir, shell_cmd)
            result = self._run(cmd)

            return result
        finally:
            if collect_report and junit_xml_out is not None:
                if junit_path.exists():
                    junit_xml_out.append(junit_path.read_text(encoding="utf-8"))
                else:
                    junit_xml_out.append("")
            shutil.rmtree(workdir, ignore_errors=True)
            shutil.rmtree(outdir, ignore_errors=True)

    def run_script(
        self,
        files: dict[str, str],
        entry: str,
    ) -> SandboxResult:
        """Esegue un singolo script Python dentro un container Docker."""

        workdir = Path(tempfile.mkdtemp(prefix="assist_docker_sandbox_"))
        outdir = Path(tempfile.mkdtemp(prefix="assist_docker_sandbox_out_"))

        shell_cmd = f"cp -r /work/* /tmp/ && python /tmp/{entry}"

        try:
            for name, content in files.items():
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            cmd = self._docker_cmd(workdir, outdir, shell_cmd)
            return self._run(cmd)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            shutil.rmtree(outdir, ignore_errors=True)

    def _docker_cmd(self, workdir: Path, outdir: Path, shell_cmd: str) -> list[str]:
        """Costruisce il comando `docker run` isolato usato per i test."""

        return [
            "docker",
            "run",
            "--rm",
            "--network=none",
            f"--memory={self.memory_limit}",
            f"--cpus={self.cpus}",
            "-v",
            f"{workdir}:/work:ro",
            "-v",
            f"{outdir}:/out",
            "-w",
            "/tmp",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            self.image,
            "sh",
            "-c",
            shell_cmd,
        ]

    def _run(self, cmd: list[str]) -> SandboxResult:
        self.runs += 1
        start = time.monotonic()
        docker_timeout = self.timeout_seconds + CONTAINER_STARTUP_GRACE_SECONDS

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=docker_timeout,
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


def make_sandbox(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    prefer_docker: bool = False,
    image: str = DEFAULT_IMAGE,
) -> SandboxRunner | DockerSandboxRunner:
    """Sceglie l'implementazione di sandbox piu' adatta.

    Se `prefer_docker` e' True e Docker e' disponibile, ritorna una
    `DockerSandboxRunner`; altrimenti ritorna una `SandboxRunner`
    (isolamento di processo). Se Docker e' richiesto ma non
    disponibile, viene loggato un warning e si esegue il fallback.
    """

    if prefer_docker:
        if docker_available():
            return DockerSandboxRunner(timeout_seconds=timeout_seconds, image=image)
        logger.warning(
            "Docker richiesto ma non disponibile: fallback a sandbox di processo"
        )

    return SandboxRunner(timeout_seconds=timeout_seconds)
