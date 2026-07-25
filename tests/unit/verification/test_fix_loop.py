"""Test del ciclo di fix validato in sandbox."""

from assist.llm.base import LLMClient
from assist.verification.fix_loop import ValidatedFixLoop

_BROKEN_SOURCE = """def add(a, b):
    return a - b
"""

_TEST_SOURCE = """from add import add


def test_add():
    assert add(1, 2) == 3
"""

_CORRECT_FIX = """def add(a, b):
    return a + b
"""

_STILL_WRONG_FIX = """def add(a, b):
    return a * b
"""


def _block(code: str) -> str:
    return f"```python\n{code}\n```"


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


def test_initial_fix_corretto_al_primo_colpo():
    llm = _ScriptedLLMClient(responses=[])
    loop = ValidatedFixLoop(llm=llm, max_iterations=3)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_name="add",
        test_source=_TEST_SOURCE,
        failure_summary="assert add(1, 2) == 3 fallisce (ritorna -1).",
        initial_fix=_block(_CORRECT_FIX),
    )

    assert result.success is True
    assert result.iterations_used == 1
    assert len(result.attempts) == 1
    assert result.attempts[0].tests_passed is True
    assert "a + b" in result.validated_fix
    assert llm.calls == []


def test_primo_fix_sbagliato_secondo_corretto():
    llm = _ScriptedLLMClient(responses=[_block(_CORRECT_FIX)])
    loop = ValidatedFixLoop(llm=llm, max_iterations=3)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_name="add",
        test_source=_TEST_SOURCE,
        failure_summary="assert add(1, 2) == 3 fallisce (ritorna -1).",
        initial_fix=_block(_STILL_WRONG_FIX),
    )

    assert result.success is True
    assert result.iterations_used == 2
    assert len(result.attempts) == 2
    assert result.attempts[0].tests_passed is False
    assert result.attempts[1].tests_passed is True
    assert "a + b" in result.validated_fix
    assert len(llm.calls) == 1


def test_fix_sempre_sbagliati_fallisce_dopo_max_iterations():
    llm = _ScriptedLLMClient(
        responses=[
            _block(_STILL_WRONG_FIX),
            _block(_STILL_WRONG_FIX),
            _block(_STILL_WRONG_FIX),
        ]
    )
    loop = ValidatedFixLoop(llm=llm, max_iterations=3)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_name="add",
        test_source=_TEST_SOURCE,
        failure_summary="assert add(1, 2) == 3 fallisce (ritorna -1).",
        initial_fix=_block(_STILL_WRONG_FIX),
    )

    assert result.success is False
    assert result.validated_fix == ""
    assert result.iterations_used == 3
    assert len(result.attempts) == 3
    assert all(not a.tests_passed for a in result.attempts)
    # con initial_fix gia' sbagliato al giro 1, servono altre 2
    # richieste al LLM per i giri 2 e 3.
    assert len(llm.calls) == 2


def test_risposta_senza_codice_o_sintassi_rotta_non_crasha():
    llm = _ScriptedLLMClient(
        responses=[
            "Non sono in grado di proporre un fix in questo momento.",
            "```python\ndef add(a, b)\n    return a + b\n```",
            _block(_CORRECT_FIX),
        ]
    )
    loop = ValidatedFixLoop(llm=llm, max_iterations=4)

    result = loop.run(
        source=_BROKEN_SOURCE,
        module_name="add",
        test_source=_TEST_SOURCE,
        failure_summary="assert add(1, 2) == 3 fallisce (ritorna -1).",
        initial_fix=_block(_STILL_WRONG_FIX),
    )

    assert result.success is True
    assert result.iterations_used == 4
    assert len(result.attempts) == 4
    assert result.attempts[0].tests_passed is False
    assert result.attempts[1].tests_passed is False
    assert result.attempts[2].tests_passed is False
    assert result.attempts[3].tests_passed is True
    assert "a + b" in result.validated_fix
