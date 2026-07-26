"""Test del runner vitest in sandbox (`assist.verification.ts_runner`).

Usa il template Node reale in /tmp/ts_template (vitest + fast-check +
typescript gia' installati, vedi CONTESTO nel task): niente mock di
`subprocess`, i test lanciano vitest per davvero. Per restare sotto
i tempi della suite si tengono al minimo i run reali (5 esecuzioni
di vitest, ciascuna 2-5s).
"""

from pathlib import Path

import pytest

from assist.verification import ts_runner
from assist.verification.ts_runner import (
    TsSandboxRunner,
    ts_available,
    ts_template_dir,
    vitest_report_to_evidence,
)

REAL_TEMPLATE_DIR = "/tmp/ts_template"

_template_presente = (
    Path(REAL_TEMPLATE_DIR) / "node_modules" / ".bin" / "vitest"
).exists()

# I test che eseguono vitest reale richiedono il template installato
# (in CI viene creato da un passo del workflow; in locale vedi
# docs/typescript.md). Senza template si skippano, non falliscono.
richiede_template = pytest.mark.skipif(
    not _template_presente,
    reason="template TS non installato in " + REAL_TEMPLATE_DIR,
)


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    """Punta al template reale e azzera la cache prima/dopo ogni test."""

    monkeypatch.setenv("ASSIST_TS_TEMPLATE", REAL_TEMPLATE_DIR)
    ts_runner.reset_ts_template_dir_cache()
    yield
    ts_runner.reset_ts_template_dir_cache()


# --- ts_template_dir / ts_available --------------------------------------


@richiede_template
def test_ts_available_true_con_template_reale():
    assert ts_template_dir() == Path(REAL_TEMPLATE_DIR)
    assert ts_available() is True


def test_ts_available_false_se_template_e_fallback_mancanti(monkeypatch):
    monkeypatch.setenv("ASSIST_TS_TEMPLATE", "/tmp/non_esiste_template_xyz")
    monkeypatch.setattr(
        ts_runner, "FALLBACK_TEMPLATE_DIR", Path("/tmp/non_esiste_fallback_xyz")
    )
    ts_runner.reset_ts_template_dir_cache()

    assert ts_template_dir() is None
    assert ts_available() is False


# --- TsSandboxRunner.run_vitest: template mancante -----------------------


def test_run_vitest_senza_template_non_solleva_eccezioni(monkeypatch):
    monkeypatch.setenv("ASSIST_TS_TEMPLATE", "/tmp/non_esiste_template_xyz")
    monkeypatch.setattr(
        ts_runner, "FALLBACK_TEMPLATE_DIR", Path("/tmp/non_esiste_fallback_xyz")
    )
    ts_runner.reset_ts_template_dir_cache()

    runner = TsSandboxRunner(timeout_seconds=10)
    result, report = runner.run_vitest(files={"sample.test.ts": "x"})

    assert result.exit_code == -1
    assert result.stderr != ""
    assert report == {}
    # nessun processo vitest lanciato: 'runs' non incrementato.
    assert runner.runs == 0


# --- TsSandboxRunner.run_vitest: test che passano -------------------------


@richiede_template
def test_run_vitest_test_passanti():
    runner = TsSandboxRunner(timeout_seconds=40)

    files = {
        "sample.test.ts": (
            "import { describe, it, expect } from 'vitest';\n\n"
            "describe('sample', () => {\n"
            "  it('adds', () => {\n"
            "    expect(1 + 1).toBe(2);\n"
            "  });\n"
            "});\n"
        ),
    }

    result, report = runner.run_vitest(files)

    assert result.ok
    assert runner.runs == 1

    evidence = vitest_report_to_evidence(report, result, label="ts-passing")

    assert evidence.passed is True
    assert evidence.tests_collected == 1
    assert evidence.tests_failed == 0


# --- TsSandboxRunner.run_vitest: test che falliscono ----------------------


@richiede_template
def test_run_vitest_test_falliti():
    runner = TsSandboxRunner(timeout_seconds=40)

    files = {
        "sample.test.ts": (
            "import { describe, it, expect } from 'vitest';\n\n"
            "describe('sample', () => {\n"
            "  it('fails', () => {\n"
            "    expect(1 + 1).toBe(3);\n"
            "  });\n"
            "});\n"
        ),
    }

    result, report = runner.run_vitest(files)

    assert not result.ok

    evidence = vitest_report_to_evidence(report, result, label="ts-failing")

    assert evidence.passed is False
    assert evidence.tests_failed >= 1
    assert evidence.failure_summary != ""


# --- TsSandboxRunner.run_vitest: errore di sintassi -----------------------


def test_run_vitest_errore_sintassi_non_solleva_eccezioni():
    runner = TsSandboxRunner(timeout_seconds=40)

    files = {
        # parentesi graffa mancante/malformata: errore di parsing TS.
        "sample.test.ts": (
            "import { describe, it, expect } from 'vitest';\n\n"
            "describe('sample' {\n"
            "  it('broken', () => {\n"
            "    expect(1 + 1).toBe(2\n"
            "  });\n"
            "});\n"
        ),
    }

    result, report = runner.run_vitest(files)

    assert not result.ok

    evidence = vitest_report_to_evidence(report, result, label="ts-syntax-error")

    assert evidence.passed is False
