"""Test per PropertyTestAgent (property-based testing con Hypothesis).

Include un test end-to-end REALE (senza LLM, senza mock) che esegue
un file di property test scritto a mano dentro SandboxRunner, per
dimostrare che Hypothesis funziona nella sandbox e trova davvero un
bug tramite una "Falsifying example".
"""

import ast

from assist.llm.mock_client import MockLLMClient
from assist.verification.property_agent import PropertyTestAgent
from assist.verification.sandbox import SandboxRunner

VALID_RESPONSE = """Ecco le proprieta':
```python
from hypothesis import given, settings, strategies as st
from calc import add, absolute


@settings(max_examples=50, deadline=None)
@given(a=st.integers(), b=st.integers())
def test_add_is_commutative(a, b):
    assert add(a, b) == add(b, a)


@settings(max_examples=50, deadline=None)
@given(x=st.integers())
def test_absolute_is_non_negative(x):
    assert absolute(x) >= 0
```
"""

NO_GIVEN_RESPONSE = """```python
from hypothesis import strategies as st
from calc import add


def test_add_example():
    assert add(1, 2) == 3
```
"""

NO_HYPOTHESIS_RESPONSE = """```python
from calc import add


def test_add_example():
    assert add(1, 2) == 3
```
"""

BROKEN_SYNTAX_RESPONSE = """```python
from hypothesis import given, strategies as st

@given(x=st.integers()
def test_broken(x):
    assert x == x
```
"""

TOO_MANY_PROPERTIES_RESPONSE = """```python
from hypothesis import given, settings, strategies as st
from calc import add


@settings(max_examples=10, deadline=None)
@given(a=st.integers())
def test_prop_one(a):
    assert add(a, 0) == a


@settings(max_examples=10, deadline=None)
@given(a=st.integers())
def test_prop_two(a):
    assert add(a, 0) == a


@settings(max_examples=10, deadline=None)
@given(a=st.integers())
def test_prop_three(a):
    assert add(a, 0) == a
```
"""


def test_extracts_valid_property_test():
    agent = PropertyTestAgent(llm=MockLLMClient(fixture=VALID_RESPONSE))

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert "@given" in result
    assert "hypothesis" in result
    assert "test_add_is_commutative" in result


def test_response_without_given_returns_empty():
    agent = PropertyTestAgent(llm=MockLLMClient(fixture=NO_GIVEN_RESPONSE))

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""


def test_response_without_hypothesis_returns_empty():
    agent = PropertyTestAgent(llm=MockLLMClient(fixture=NO_HYPOTHESIS_RESPONSE))

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""


def test_broken_syntax_returns_empty():
    agent = PropertyTestAgent(llm=MockLLMClient(fixture=BROKEN_SYNTAX_RESPONSE))

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""


def test_too_many_properties_returns_empty():
    agent = PropertyTestAgent(
        llm=MockLLMClient(fixture=TOO_MANY_PROPERTIES_RESPONSE),
        max_properties=2,
    )

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""


def test_harden_adds_settings_profile():
    test_source = (
        "from hypothesis import given, strategies as st\n"
        "from calc import add\n\n\n"
        "@given(a=st.integers())\n"
        "def test_add_identity(a):\n"
        "    assert add(a, 0) == a\n"
    )

    hardened = PropertyTestAgent.harden(test_source, max_examples=25)

    assert "register_profile" in hardened
    assert "load_profile" in hardened
    assert "max_examples=25" in hardened

    # Il file risultante deve restare sintatticamente valido.
    ast.parse(hardened)


def test_harden_result_is_syntactically_valid_even_on_empty_input():
    hardened = PropertyTestAgent.harden("", max_examples=10)

    assert "register_profile" in hardened
    ast.parse(hardened)


# ---------------------------------------------------------------------
# Test end-to-end REALE: nessun LLM/mock coinvolto. Scriviamo a mano un
# modulo con una funzione corretta (`absolute`) e una bacata (`clamp`),
# e i relativi property test Hypothesis, poi li eseguiamo con
# SandboxRunner reale per dimostrare che Hypothesis gira nella sandbox
# e trova davvero il bug (Falsifying example, exit code != 0).
# ---------------------------------------------------------------------

BUGGY_MODULE_SOURCE = """
def absolute(x):
    \"\"\"Ritorna il valore assoluto di x.\"\"\"
    return x if x > 0 else -x


def clamp(v, lo, hi):
    \"\"\"BACATA: non applica il limite superiore ``hi``.\"\"\"
    if v < lo:
        return lo
    return v
"""

PROPERTY_TEST_SOURCE = """
from hypothesis import given, settings, strategies as st

from buggy_mod import absolute, clamp


@settings(max_examples=100, deadline=None)
@given(x=st.integers())
def test_absolute_is_never_negative(x):
    assert absolute(x) >= 0


@settings(max_examples=100, deadline=None)
@given(
    v=st.integers(min_value=-1000, max_value=1000),
    lo=st.integers(min_value=-1000, max_value=1000),
    hi=st.integers(min_value=-1000, max_value=1000),
)
def test_clamp_stays_within_bounds(v, lo, hi):
    if lo > hi:
        lo, hi = hi, lo
    result = clamp(v, lo, hi)
    assert lo <= result <= hi
"""


def test_end_to_end_hypothesis_finds_real_bug_in_sandbox():
    runner = SandboxRunner(timeout_seconds=30)

    result = runner.run_pytest(
        files={
            "buggy_mod.py": BUGGY_MODULE_SOURCE,
            "test_buggy_mod_properties.py": PROPERTY_TEST_SOURCE,
        }
    )

    output = result.stdout + result.stderr

    # La proprieta' su `absolute` e' corretta: non deve essere lei a
    # causare il fallimento. La proprieta' su `clamp` invece DEVE
    # fallire, perche' `clamp` non rispetta il limite superiore.
    assert result.exit_code != 0
    assert not result.timed_out
    # Il testo esatto del controesempio dipende dalla versione di
    # Hypothesis installata: le versioni storiche usano "Falsifying
    # example", quelle piu' recenti (>=6.x qui installata) usano
    # "Failing test case". Verifichiamo entrambe le forme per
    # dimostrare in modo robusto che Hypothesis ha trovato e
    # riportato un controesempio reale nella sandbox.
    assert "Falsifying example" in output or "Failing test case" in output
    assert "test_clamp_stays_within_bounds" in output
