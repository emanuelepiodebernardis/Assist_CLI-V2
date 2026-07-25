from assist.llm.mock_client import MockLLMClient
from assist.verification.boundary_agent import BoundaryTestAgent

VALID_RESPONSE = """Ecco i test:
```python
from calc import add

def test_add_zero():
    assert add(0, 0) == 0
```
"""


def test_extracts_fenced_code():
    agent = BoundaryTestAgent(
        llm=MockLLMClient(fixture=VALID_RESPONSE)
    )

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert "def test_add_zero" in result


def test_invalid_output_returns_empty():
    agent = BoundaryTestAgent(
        llm=MockLLMClient(fixture="Non posso aiutarti.")
    )

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""


def test_syntax_error_output_returns_empty():
    agent = BoundaryTestAgent(
        llm=MockLLMClient(
            fixture="```python\ndef test_broken(:\n```"
        )
    )

    result = agent.generate(
        source="def add(a, b):\n    return a + b\n",
        module_name="calc",
    )

    assert result == ""
