"""Test unitari per OpenAICompatibleClient (nessuna rete reale).

``urllib.request.urlopen`` viene sostituito con un doppio di test che
registra le richieste effettuate e restituisce risposte/errori
predefiniti, così da verificare payload, header e logica di retry senza
dipendere da un server esterno.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from assist.llm.openai_compatible_client import OpenAICompatibleClient


class _FakeResponse:
    """Simula l'oggetto restituito da ``urlopen`` come context manager."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _make_http_error(
    status: int,
    body: bytes,
    url: str = "http://example.test/v1/chat/completions",
) -> urllib.error.HTTPError:
    """Costruisce un HTTPError con corpo leggibile via ``.read()``."""

    return urllib.error.HTTPError(
        url, status, "error", None, io.BytesIO(body)
    )


def _ok_body(content: Any) -> bytes:
    """Serializza una risposta chat/completions valida."""

    return json.dumps(
        {"choices": [{"message": {"content": content}}]}
    ).encode("utf-8")


class _FakeUrlopen:
    """Doppio di ``urlopen`` che riproduce una sequenza di comportamenti.

    Ogni elemento di ``behaviors`` è o un'eccezione da sollevare o un
    oggetto ``_FakeResponse`` da restituire. Registra tutte le richieste
    ricevute in ``requests`` per le asserzioni.
    """

    def __init__(self, behaviors: list[Any]) -> None:
        self._behaviors = list(behaviors)
        self.requests: list[urllib.request.Request] = []

    def __call__(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> _FakeResponse:
        self.requests.append(request)
        behavior = self._behaviors.pop(0)

        if isinstance(behavior, Exception):
            raise behavior

        return behavior


def _install_fake_urlopen(
    monkeypatch: pytest.MonkeyPatch, behaviors: list[Any]
) -> _FakeUrlopen:
    fake = _FakeUrlopen(behaviors)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


def test_request_url_and_payload_are_well_formed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_fake_urlopen(
        monkeypatch, [_FakeResponse(_ok_body("ciao"))]
    )

    client = OpenAICompatibleClient(
        model="gpt-test",
        base_url="http://example.test/v1/",
        api_key="secret-key",
    )

    result = client.complete(prompt="dimmi ciao", system="sii breve")

    assert result == "ciao"
    assert len(fake.requests) == 1

    request = fake.requests[0]
    assert request.full_url == "http://example.test/v1/chat/completions"

    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "gpt-test"
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 8000
    assert payload["messages"] == [
        {"role": "system", "content": "sii breve"},
        {"role": "user", "content": "dimmi ciao"},
    ]


def test_system_omitted_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_urlopen(
        monkeypatch, [_FakeResponse(_ok_body("ok"))]
    )

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )
    client.complete(prompt="ciao")

    payload = json.loads(fake.requests[0].data.decode("utf-8"))
    assert payload["messages"] == [{"role": "user", "content": "ciao"}]


def test_authorization_header_present_with_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_fake_urlopen(
        monkeypatch, [_FakeResponse(_ok_body("ok"))]
    )

    client = OpenAICompatibleClient(
        model="gpt-test",
        base_url="http://example.test/v1",
        api_key="secret-key",
    )
    client.complete(prompt="ciao")

    assert (
        fake.requests[0].get_header("Authorization")
        == "Bearer secret-key"
    )


def test_authorization_header_absent_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake = _install_fake_urlopen(
        monkeypatch, [_FakeResponse(_ok_body("ok"))]
    )

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )
    client.complete(prompt="ciao")

    assert fake.requests[0].get_header("Authorization") is None


def test_content_none_returns_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_urlopen(monkeypatch, [_FakeResponse(_ok_body(None))])

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )
    result = client.complete(prompt="ciao")

    assert result == ""


def test_missing_choices_raises_runtime_error_with_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed_body = json.dumps({"unexpected": "shape"}).encode("utf-8")
    _install_fake_urlopen(
        monkeypatch, [_FakeResponse(malformed_body)]
    )

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )

    with pytest.raises(RuntimeError) as excinfo:
        client.complete(prompt="ciao")

    assert "choices" in str(excinfo.value)
    assert "unexpected" in str(excinfo.value)


def test_retries_once_on_http_500_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "assist.llm.openai_compatible_client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    fake = _install_fake_urlopen(
        monkeypatch,
        [
            _make_http_error(500, b"internal error"),
            _FakeResponse(_ok_body("recovered")),
        ],
    )

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )
    result = client.complete(prompt="ciao")

    assert result == "recovered"
    assert len(fake.requests) == 2
    assert sleep_calls == [2.0]


def test_http_400_raises_immediately_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "assist.llm.openai_compatible_client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    fake = _install_fake_urlopen(
        monkeypatch, [_make_http_error(400, b"bad request detail")]
    )

    client = OpenAICompatibleClient(
        model="gpt-test", base_url="http://example.test/v1"
    )

    with pytest.raises(RuntimeError) as excinfo:
        client.complete(prompt="ciao")

    assert "400" in str(excinfo.value)
    assert "bad request detail" in str(excinfo.value)
    assert len(fake.requests) == 1
    assert sleep_calls == []


def test_api_key_from_custom_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_LLM_KEY", "env-key-value")
    fake = _install_fake_urlopen(
        monkeypatch, [_FakeResponse(_ok_body("ok"))]
    )

    client = OpenAICompatibleClient(
        model="gpt-test",
        base_url="http://example.test/v1",
        api_key_env="CUSTOM_LLM_KEY",
    )
    client.complete(prompt="ciao")

    assert (
        fake.requests[0].get_header("Authorization")
        == "Bearer env-key-value"
    )
