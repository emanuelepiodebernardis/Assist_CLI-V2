"""Test dei provider model-agnostic: none (evidence-only) e openai."""

from assist.llm.factory import LLMFactory
from assist.llm.null_client import NullLLMClient
from assist.llm.openai_compatible_client import (
    OpenAICompatibleClient,
)


def test_provider_none_returns_null_client():
    client = LLMFactory.create_tier("fast", provider="none")

    assert isinstance(client, NullLLMClient)
    assert client.complete("qualunque prompt") == ""


def test_provider_openai_uses_configured_models():
    client = LLMFactory.create_tier("strong", provider="openai")

    assert isinstance(client, OpenAICompatibleClient)
    # modello strong dalla config di default
    assert client.model == "claude-sonnet-4-6"


def test_provider_openai_alias_compatible():
    client = LLMFactory.create_tier(
        "fast", provider="openai-compatible"
    )

    assert isinstance(client, OpenAICompatibleClient)
