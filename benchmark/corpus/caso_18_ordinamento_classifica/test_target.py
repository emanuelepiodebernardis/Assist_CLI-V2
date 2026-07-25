"""Test-bugia: non provano mai due punteggi uguali (il caso limite
che rivelerebbe l'errore)."""

from target import punteggio_maggiore


def test_punteggio_piu_alto_precede() -> None:
    assert punteggio_maggiore(100, 50) is True


def test_punteggio_piu_basso_non_precede() -> None:
    assert punteggio_maggiore(30, 80) is False
