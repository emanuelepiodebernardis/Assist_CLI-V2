from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from assist.llm.base import LLMClient

load_dotenv()


class AnthropicClient(LLMClient):

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.2,
        max_tokens: int = 8000,
        api_key: str | None = None,
    ) -> None:

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set."
            )

        self.client = Anthropic(
            api_key=self.api_key
        )

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:

        full_prompt = prompt

        if system.strip():
            full_prompt = (
                f"{system.strip()}\n\n{prompt}"
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": full_prompt,
                }
            ],
        )

        return self._extract_text(
            response.content
        )

    @staticmethod
    def _extract_text(
        content: list[Any],
    ) -> str:

        parts: list[str] = []

        for block in content:

            text = getattr(
                block,
                "text",
                None,
            )

            if text:
                parts.append(text)

        return "\n".join(parts).strip()