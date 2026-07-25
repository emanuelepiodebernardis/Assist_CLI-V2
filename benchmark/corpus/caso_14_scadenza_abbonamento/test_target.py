"""Test-bugia: non provano mai il giorno esattamente al limite (3)."""

from target import abbonamento_valido


def test_abbonamento_in_regola() -> None:
    assert abbonamento_valido(0) is True


def test_abbonamento_scaduto_da_molto() -> None:
    assert abbonamento_valido(10) is False
