import pytest

from assist.core.registry import (
    Registry,
    UnknownCommandError,
)


def test_registry_resolves_review():
    registry = Registry()

    agent, skills = registry.resolve("review")

    assert agent == "ReviewerAgent"

    assert "code_review" in skills


def test_registry_unknown_command():
    registry = Registry()

    with pytest.raises(UnknownCommandError):
        registry.resolve("unknown")