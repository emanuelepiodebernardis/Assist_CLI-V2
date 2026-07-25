from assist.llm.base import LLMClient


class MockLLMClient(LLMClient):
    def __init__(
        self,
        fixture: str = "Mock response",
    ) -> None:
        self.fixture = fixture

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:
        return self.fixture