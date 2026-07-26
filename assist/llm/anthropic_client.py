from __future__ import annotations

import os
import time
from typing import Any

import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv

from assist.llm.base import LLMClient

load_dotenv()

# Eccezioni del pacchetto ``anthropic`` sempre riconducibili a un problema
# transitorio (rate limit, sovraccarico, connessione): un retry ha senso
# a prescindere dallo status code. Definita a livello di modulo cosi' i
# test possono monkeypatchare direttamente questa tupla con eccezioni
# finte, senza dover costruire istanze reali di ``httpx.Response``.
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


def _is_retryable_error(exc: BaseException) -> bool:
    """Determina se un'eccezione giustifica un retry.

    Ritorna ``True`` per le eccezioni elencate in
    :data:`RETRYABLE_EXCEPTIONS` e per qualunque
    ``anthropic.APIStatusError`` (o sottoclasse, es. per errori 429/5xx/
    "overloaded" non gia' coperti sopra) con ``status_code >= 500``.
    Tutti gli altri errori (es. richieste malformate, 4xx diversi da
    429) non sono transitori e vanno propagati subito.
    """
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True

    status_code = getattr(exc, "status_code", None)

    if isinstance(exc, anthropic.APIStatusError) and status_code is not None:
        return status_code >= 500

    return False


class AnthropicClient(LLMClient):

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.2,
        max_tokens: int = 8000,
        api_key: str | None = None,
        max_retries: int = 2,
    ) -> None:

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

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

        response = self._complete_with_retry(full_prompt)

        return self._extract_text(
            response.content
        )

    def _complete_with_retry(
        self,
        full_prompt: str,
    ) -> Any:
        """Chiama il modello ritentando su errori transitori.

        Ritenta al massimo ``self.max_retries`` volte con attesa
        esponenziale (2s, poi 4s, ...) solo se l'errore e' riconducibile
        a rate limit, sovraccarico o problemi lato server (vedi
        :func:`_is_retryable_error`). Ogni altro errore viene propagato
        immediatamente senza attesa. Esaurito il budget di retry, viene
        propagata l'ultima eccezione incontrata.
        """
        delay_seconds = 2.0
        attempt = 0

        while True:
            try:
                return self.client.messages.create(
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
            except Exception as exc:
                if not _is_retryable_error(exc) or attempt >= self.max_retries:
                    raise

                time.sleep(delay_seconds)
                delay_seconds *= 2
                attempt += 1

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
