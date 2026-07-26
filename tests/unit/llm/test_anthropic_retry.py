"""Test unitari per il retry di AnthropicClient (nessuna rete reale).

``self.client.messages.create`` viene sostituito con un doppio di test
che simula successi/fallimenti; ``time.sleep`` viene azzerato per non
rallentare i test. La tupla ``RETRYABLE_EXCEPTIONS`` viene monkeypatchata
con eccezioni finte per evitare di dover costruire istanze reali delle
eccezioni del pacchetto ``anthropic`` (che richiedono un ``httpx.Response``
o ``httpx.Request``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import assist.llm.anthropic_client as anthropic_client_module
from assist.llm.anthropic_client import AnthropicClient


class _FakeRetryableError(Exception):
    """Eccezione finta usata al posto di anthropic.RateLimitError & co."""


class _FakeNonRetryableError(Exception):
    """Eccezione finta usata al posto di anthropic.BadRequestError."""


def _fake_response(text: str) -> Any:
    """Costruisce un oggetto simile a una risposta di anthropic.messages.create."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _make_client(max_retries: int = 2) -> AnthropicClient:
    return AnthropicClient(api_key="test-key", max_retries=max_retries)


_PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Sostituisce time.sleep con un doppio che registra le attese.

    Rimuove anche eventuali variabili d'ambiente di proxy: qui non
    serve rete reale e un proxy SOCKS configurato nell'ambiente
    farebbe fallire la sola costruzione del client httpx interno.
    """
    for var in _PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    sleeps: list[float] = []

    def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(anthropic_client_module.time, "sleep", _fake_sleep)
    return sleeps


def test_success_on_first_try_does_not_sleep(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_sleep: list[float],
) -> None:
    client = _make_client()

    def _create(**kwargs: Any) -> Any:
        return _fake_response("ok")

    monkeypatch.setattr(client.client.messages, "create", _create)

    result = client.complete(prompt="ciao")

    assert result == "ok"
    assert _no_real_sleep == []


def test_retries_on_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_sleep: list[float],
) -> None:
    monkeypatch.setattr(
        anthropic_client_module,
        "RETRYABLE_EXCEPTIONS",
        (_FakeRetryableError,),
    )

    client = _make_client(max_retries=2)

    calls = {"n": 0}

    def _create(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _FakeRetryableError("429 rate limited")
        return _fake_response("risposta dopo retry")

    monkeypatch.setattr(client.client.messages, "create", _create)

    result = client.complete(prompt="ciao")

    assert result == "risposta dopo retry"
    assert calls["n"] == 3
    assert _no_real_sleep == [2.0, 4.0]


@pytest.mark.parametrize(
    "error",
    [
        _FakeNonRetryableError("bad request"),
        ValueError("qualcosa d'altro"),
    ],
)
def test_non_retryable_error_propagates_immediately(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_sleep: list[float],
    error: Exception,
) -> None:
    monkeypatch.setattr(
        anthropic_client_module,
        "RETRYABLE_EXCEPTIONS",
        (_FakeRetryableError,),
    )

    client = _make_client(max_retries=2)

    calls = {"n": 0}

    def _create(**kwargs: Any) -> Any:
        calls["n"] += 1
        raise error

    monkeypatch.setattr(client.client.messages, "create", _create)

    with pytest.raises(type(error)):
        client.complete(prompt="ciao")

    assert calls["n"] == 1
    assert _no_real_sleep == []


def test_retries_exhausted_propagates_last_exception(
    monkeypatch: pytest.MonkeyPatch,
    _no_real_sleep: list[float],
) -> None:
    monkeypatch.setattr(
        anthropic_client_module,
        "RETRYABLE_EXCEPTIONS",
        (_FakeRetryableError,),
    )

    client = _make_client(max_retries=2)

    calls = {"n": 0}

    def _create(**kwargs: Any) -> Any:
        calls["n"] += 1
        raise _FakeRetryableError(f"tentativo {calls['n']}")

    monkeypatch.setattr(client.client.messages, "create", _create)

    with pytest.raises(_FakeRetryableError, match="tentativo 3"):
        client.complete(prompt="ciao")

    assert calls["n"] == 3
    assert _no_real_sleep == [2.0, 4.0]
