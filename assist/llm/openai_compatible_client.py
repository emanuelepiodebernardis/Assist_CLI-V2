"""Client per qualsiasi API compatibile con lo schema OpenAI Chat Completions.

Copre lo standard de facto adottato da OpenAI, Ollama, LM Studio, vLLM,
Groq, Mistral, DeepSeek, OpenRouter, llama.cpp server e simili. Usa
esclusivamente la standard library (``urllib``) per non introdurre una
dipendenza dal pacchetto ``openai``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from assist.llm.base import LLMClient

_CHAT_COMPLETIONS_PATH = "/chat/completions"
_RETRY_WAIT_SECONDS = 2.0
_ERROR_SNIPPET_LENGTH = 200


class _RetryableRequestError(Exception):
    """Errore transitorio (rete o HTTP 429/5xx) che giustifica un retry."""


class OpenAICompatibleClient(LLMClient):
    """Client LLM per endpoint compatibili con l'API OpenAI Chat Completions.

    La chiave API è opzionale: molti server locali (Ollama, LM Studio,
    llama.cpp server) non la richiedono. Viene risolta nell'ordine:
    parametro esplicito, variabile d'ambiente indicata da ``api_key_env``,
    infine stringa vuota (nessun header ``Authorization`` inviato).
    """

    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.2,
        max_tokens: int = 8000,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        timeout_seconds: int = 120,
    ) -> None:

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

        self.api_key = (
            api_key
            or os.getenv(api_key_env)
            or ""
        )

    @property
    def _endpoint_url(self) -> str:
        """URL completo dell'endpoint chat/completions."""
        return f"{self.base_url}{_CHAT_COMPLETIONS_PATH}"

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:
        """Invia il prompt all'endpoint e ritorna il testo generato.

        Applica un singolo retry (dopo un'attesa di 2 secondi) in caso di
        errore di rete o di risposta HTTP 429/5xx. Su altri errori HTTP,
        o su risposta malformata, solleva subito ``RuntimeError``.
        """

        payload = self._build_payload(prompt, system)

        try:
            return self._send_request(payload)
        except _RetryableRequestError as first_error:
            time.sleep(_RETRY_WAIT_SECONDS)
            try:
                return self._send_request(payload)
            except _RetryableRequestError as second_error:
                raise RuntimeError(str(second_error)) from first_error

    def _build_payload(
        self,
        prompt: str,
        system: str,
    ) -> dict[str, Any]:
        """Costruisce il payload JSON per la richiesta chat/completions."""

        messages: list[dict[str, str]] = []

        if system.strip():
            messages.append(
                {"role": "system", "content": system}
            )

        messages.append({"role": "user", "content": prompt})

        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _send_request(self, payload: dict[str, Any]) -> str:
        """Esegue una singola chiamata HTTP e ritorna il content estratto.

        Solleva ``_RetryableRequestError`` per errori transitori (rete,
        429, 5xx) e ``RuntimeError`` per tutti gli altri casi di errore.
        """

        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            self._endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw_body = response.read()
        except urllib.error.HTTPError as exc:
            raise self._error_from_http_exception(exc) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            reason = getattr(exc, "reason", exc)
            raise _RetryableRequestError(
                "Errore di rete verso l'API OpenAI-compatible "
                f"({self._endpoint_url}): {reason}"
            ) from exc

        return self._extract_content(raw_body)

    def _error_from_http_exception(
        self,
        exc: urllib.error.HTTPError,
    ) -> Exception:
        """Traduce un HTTPError nell'eccezione appropriata (retry o no)."""

        body_bytes = exc.read()
        snippet = body_bytes[:_ERROR_SNIPPET_LENGTH].decode(
            "utf-8", errors="replace"
        )
        message = (
            f"Errore HTTP {exc.code} dall'API OpenAI-compatible "
            f"({self._endpoint_url}): {snippet}"
        )

        if exc.code == 429 or exc.code >= 500:
            return _RetryableRequestError(message)

        return RuntimeError(message)

    def _extract_content(self, raw_body: bytes) -> str:
        """Estrae ``choices[0].message.content`` dal corpo della risposta."""

        snippet = raw_body[:_ERROR_SNIPPET_LENGTH].decode(
            "utf-8", errors="replace"
        )

        try:
            decoded = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(
                "Risposta non valida (JSON malformato) dall'API "
                f"OpenAI-compatible ({self._endpoint_url}): {snippet}"
            ) from exc

        choices = decoded.get("choices") if isinstance(decoded, dict) else None

        if not choices:
            raise RuntimeError(
                "Risposta malformata (campo 'choices' mancante o vuoto) "
                f"dall'API OpenAI-compatible ({self._endpoint_url}): {snippet}"
            )

        message = choices[0].get("message") or {}
        content = message.get("content")

        return content or ""
