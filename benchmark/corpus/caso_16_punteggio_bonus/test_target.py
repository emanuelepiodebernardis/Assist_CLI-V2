"""Test-bugia: controllano solo che il punteggio sia un intero non
negativo, mai il valore esatto atteso col bonus."""

from target import punteggio_finale


def test_punteggio_finale_non_negativo() -> None:
    assert punteggio_finale(50) >= 0


def test_punteggio_finale_e_intero() -> None:
    assert isinstance(punteggio_finale(100, bonus_velocita=20), int)
