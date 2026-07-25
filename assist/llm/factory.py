from assist.core.config import ConfigLoader
from assist.llm.anthropic_client import AnthropicClient
from assist.llm.base import LLMClient
from assist.llm.mock_client import MockLLMClient
from assist.llm.null_client import NullLLMClient
from assist.llm.openai_compatible_client import (
    OpenAICompatibleClient,
)


class LLMFactory:
    @staticmethod
    def create(
        provider: str = "anthropic",
    ) -> LLMClient:

        if provider == "mock":
            return MockLLMClient(
                fixture="Mock review result"
            )

        if provider == "anthropic":
            settings = ConfigLoader().load()

            return AnthropicClient(
                model=settings.model,
                temperature=settings.temperature,
            )

        raise ValueError(
            f"Unknown provider: {provider}"
        )

    @staticmethod
    def create_tier(
        tier: str,
        provider: str = "anthropic",
    ) -> LLMClient:
        """Crea un client per il tier richiesto (v4.0 Proof Engine).

        - "fast": modello economico per gli agenti dello sciame
        - "strong": modello forte per judge e fix
        """

        if tier not in ("fast", "strong"):
            raise ValueError(
                f"Unknown tier: {tier}"
            )

        if provider == "none":
            return NullLLMClient()

        if provider == "mock":
            return MockLLMClient(
                fixture=f"Mock {tier} response"
            )

        if provider in ("openai", "openai-compatible"):
            settings = ConfigLoader().load()

            model = (
                settings.models.fast
                if tier == "fast"
                else settings.models.strong
            )

            return OpenAICompatibleClient(
                model=model,
                base_url=settings.llm.base_url,
                temperature=settings.temperature,
                api_key_env=settings.llm.api_key_env,
            )

        if provider == "anthropic":
            settings = ConfigLoader().load()

            model = (
                settings.models.fast
                if tier == "fast"
                else settings.models.strong
            )

            return AnthropicClient(
                model=model,
                temperature=settings.temperature,
            )

        raise ValueError(
            f"Unknown provider: {provider}"
        )
