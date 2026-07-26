"""Test del ciclo di fix validato in sandbox per TypeScript
(`assist.verification.ts_fix_loop.TsValidatedFixLoop`).

Usa il template Node reale in /tmp/ts_template (vitest + fast-check +
typescript gia' installati): niente mock di subprocess, i test
lanciano vitest per davvero. Ogni run vitest impiega circa 0.7-1s: la
suite resta sotto i 35s complessivi (al massimo 4 run reali).
"""

import pytest

from assist.llm.base import LLMClient
from assist.verification import ts_runner
from assist.verification.ts_fix_loop import TsValidatedFixLoop
from assist.verification.ts_runner import TsSandboxRunner, ts_available

REAL_TEMPLATE_DIR = "/tmp/ts_template"

pytestmark = pytest.mark.skipif(
    not ts_available(), reason="template TypeScript non disponibile"
)

_MODULE_FILE = "add.ts"

_BROKEN_SOURCE = (
    "export function add(a: number, b: number): number {\n"
    "  return a - b;\n"
    "}\n"
)

_STILL_WRONG_FIX = (
    "export function add(a: number, b: number): number {\n"
    "  return a * b;\n"
    "}\n"
)

_CORRECT_FIX = (
    "export function add(a: number, b: number): number {\n"
    "  return a + b;\n"
    "}\n"
)

_TEST_FILES = {
    "add.test.ts": (
        "import { describe, it, expect } from 'vitest';\n"
        "import { add } from './add';\n\n"
        "describe('add', () => {\n"
        "  it('adds', () => {\n"
        "    expect(add(1, 2)).toBe(3);\n"
        "  });\n"
        "});\n"
    ),
}

_FAILURE_SUMMARY = "expect(add(1, 2)).toBe(3) fallisce (ritorna -1)."


@pytest.fixture(autouse=True)
def _use_real_template(monkeypatch):
    """Punta al template Node reale e azzera la cache prima/dopo ogni test."""

    monkeypatch.setenv("ASSIST_TS_TEMPLATE", REAL_TEMPLATE_DIR)
    ts_runner.reset_ts_template_dir_cache()
    yield
    ts_runner.reset_ts_template_dir_cache()


def _block(code: str) -> str:
    return f"```typescript\n{code}\n```"


def _make_loop(
    llm: "_ScriptedLLMClient", max_iterations: int = 3
) -> TsValidatedFixLoop:
    return TsValidatedFixLoop(
        llm=llm,
        runner=TsSandboxRunner(timeout_seconds=30),
        max_iterations=max_iterations,
    )


class _ScriptedLLMClient(LLMClient):
    """LLM mock che ritorna risposte diverse a chiamate successive,
    prelevandole da una lista di fixture in ordine."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def complete(self, prompt: str, system: str = "") -> str:
        self.calls.append(prompt)
        index = len(self.calls) - 1
        if index < len(self.responses):
            return self.responses[index]
        return self.responses[-1]


def test_primo_fix_corretto_al_primo_colpo():
    llm = _ScriptedLLMClient(responses=[_block(_CORRECT_FIX)])
    loop = _make_loop(llm)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_file=_MODULE_FILE,
        test_files=_TEST_FILES,
        failure_summary=_FAILURE_SUMMARY,
    )

    assert result.success is True
    assert result.iterations_used == 1
    assert len(result.attempts) == 1
    assert result.attempts[0].tests_passed is True
    assert "a + b" in result.validated_fix
    assert len(llm.calls) == 1


def test_primo_fix_sbagliato_secondo_corretto():
    llm = _ScriptedLLMClient(
        responses=[_block(_STILL_WRONG_FIX), _block(_CORRECT_FIX)]
    )
    loop = _make_loop(llm)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_file=_MODULE_FILE,
        test_files=_TEST_FILES,
        failure_summary=_FAILURE_SUMMARY,
    )

    assert result.success is True
    assert result.iterations_used == 2
    assert len(result.attempts) == 2
    assert result.attempts[0].tests_passed is False
    assert result.attempts[1].tests_passed is True
    assert "a + b" in result.validated_fix
    assert len(llm.calls) == 2


def test_fix_sempre_sbagliati_fallisce_dopo_max_iterations():
    llm = _ScriptedLLMClient(
        responses=[_block(_STILL_WRONG_FIX), _block(_STILL_WRONG_FIX)]
    )
    loop = _make_loop(llm, max_iterations=2)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_file=_MODULE_FILE,
        test_files=_TEST_FILES,
        failure_summary=_FAILURE_SUMMARY,
    )

    assert result.success is False
    assert result.validated_fix == ""
    assert result.iterations_used == 2
    assert len(result.attempts) == 2
    assert all(not attempt.tests_passed for attempt in result.attempts)
    assert len(llm.calls) == 2


def test_risposta_senza_codice_interrompe_subito():
    llm = _ScriptedLLMClient(responses=[""])
    loop = _make_loop(llm)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_file=_MODULE_FILE,
        test_files=_TEST_FILES,
        failure_summary=_FAILURE_SUMMARY,
    )

    assert result.success is False
    assert result.validated_fix == ""
    assert len(result.attempts) == 1
    assert result.attempts[0].tests_passed is False
    assert result.attempts[0].fix_source == ""
    assert len(llm.calls) == 1
