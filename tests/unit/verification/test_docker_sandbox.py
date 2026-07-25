"""Test per assist.verification.docker_sandbox.

Nessun Docker reale: subprocess.run viene sempre monkeypatchato.
"""

import logging
import subprocess
from pathlib import Path

import pytest

from assist.verification import docker_sandbox
from assist.verification.docker_sandbox import (
    DockerSandboxRunner,
    docker_available,
    make_sandbox,
    reset_docker_cache,
)
from assist.verification.sandbox import SandboxRunner


@pytest.fixture(autouse=True)
def _reset_cache():
    """Azzera la cache di docker_available prima e dopo ogni test."""

    reset_docker_cache()
    yield
    reset_docker_cache()


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _find_mounted_dir(cmd: list[str], mount_suffix: str) -> str:
    """Estrae dal comando docker la dir host montata su `mount_suffix`."""

    for i, arg in enumerate(cmd):
        if arg == "-v" and cmd[i + 1].endswith(mount_suffix):
            return cmd[i + 1][: -len(mount_suffix)]
    raise AssertionError(f"nessun mount con suffisso {mount_suffix!r} trovato in {cmd}")


# --- docker_available ---------------------------------------------------


def test_docker_available_true(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=0)
    )

    assert docker_available() is True


def test_docker_available_false_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=1)
    )

    assert docker_available() is False


def test_docker_available_false_on_exception(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError("docker non trovato")

    monkeypatch.setattr(subprocess, "run", _raise)

    assert docker_available() is False


def test_docker_available_is_cached(monkeypatch):
    calls = {"count": 0}

    def _fake_run(*a, **k):
        calls["count"] += 1
        return _FakeCompleted(returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    assert docker_available() is True
    assert docker_available() is True
    assert calls["count"] == 1


def test_reset_docker_cache_forces_recheck(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=0)
    )
    assert docker_available() is True

    reset_docker_cache()

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=1)
    )
    assert docker_available() is False


# --- make_sandbox ---------------------------------------------------------


def test_make_sandbox_default_returns_sandbox_runner():
    runner = make_sandbox()

    assert isinstance(runner, SandboxRunner)


def test_make_sandbox_prefer_docker_true_and_available(monkeypatch):
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: True)

    runner = make_sandbox(prefer_docker=True)

    assert isinstance(runner, DockerSandboxRunner)


def test_make_sandbox_prefer_docker_true_but_unavailable_falls_back(
    monkeypatch, caplog
):
    monkeypatch.setattr(docker_sandbox, "docker_available", lambda: False)

    with caplog.at_level(logging.WARNING):
        runner = make_sandbox(prefer_docker=True)

    assert isinstance(runner, SandboxRunner)
    assert not isinstance(runner, DockerSandboxRunner)
    assert any(
        "Docker richiesto ma non disponibile" in record.message
        for record in caplog.records
    )


# --- DockerSandboxRunner.run_pytest --------------------------------------


def test_run_pytest_command_contains_isolation_flags(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return _FakeCompleted(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    runner = DockerSandboxRunner(
        timeout_seconds=10, memory_limit="256m", cpus="0.5"
    )
    result = runner.run_pytest(files={"test_x.py": "def test_x():\n    assert True\n"})

    assert result.ok
    assert result.exit_code == 0
    assert len(captured_cmds) == 1

    cmd = captured_cmds[0]
    assert "docker" in cmd
    assert "run" in cmd
    assert "--network=none" in cmd
    assert "--memory=256m" in cmd
    assert "--cpus=0.5" in cmd
    assert docker_sandbox.DEFAULT_IMAGE in cmd


def test_run_pytest_timeout(monkeypatch):
    def _fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", _fake_run)

    runner = DockerSandboxRunner(timeout_seconds=5)
    result = runner.run_pytest(files={"test_x.py": "def test_x():\n    pass\n"})

    assert result.timed_out is True
    assert result.exit_code == -1
    assert not result.ok


def test_runs_counter_increments(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=0)
    )

    runner = DockerSandboxRunner()
    assert runner.runs == 0

    runner.run_pytest(files={"test_x.py": "def test_x():\n    assert True\n"})
    assert runner.runs == 1

    runner.run_script(files={"main.py": "print('ok')\n"}, entry="main.py")
    assert runner.runs == 2


def test_run_script_command_uses_entry(monkeypatch):
    captured_cmds = []

    def _fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return _FakeCompleted(returncode=0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    runner = DockerSandboxRunner()
    result = runner.run_script(files={"main.py": "print('ok')\n"}, entry="main.py")

    assert result.ok
    shell_cmd = captured_cmds[0][-1]
    assert "python /tmp/main.py" in shell_cmd


# --- collect_report / junit_xml_out --------------------------------------


def test_run_pytest_collect_report_reads_junit_xml(monkeypatch):
    junit_content = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuite name="pytest" tests="1"></testsuite>'
    )

    def _fake_run(cmd, **kwargs):
        outdir = _find_mounted_dir(cmd, ":/out")
        junit_path = Path(outdir) / docker_sandbox.JUNIT_XML_FILENAME
        junit_path.write_text(junit_content, encoding="utf-8")
        return _FakeCompleted(returncode=0, stdout="1 passed")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    runner = DockerSandboxRunner()
    junit_out: list[str] = []
    result = runner.run_pytest(
        files={"test_x.py": "def test_x():\n    assert True\n"},
        collect_report=True,
        junit_xml_out=junit_out,
    )

    assert result.ok
    assert len(junit_out) == 1
    assert junit_out[0] == junit_content


def test_run_pytest_collect_report_missing_file_yields_empty_string(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _FakeCompleted(returncode=1)
    )

    runner = DockerSandboxRunner()
    junit_out: list[str] = []
    runner.run_pytest(
        files={"test_x.py": "def test_x():\n    assert True\n"},
        collect_report=True,
        junit_xml_out=junit_out,
    )

    assert junit_out == [""]
