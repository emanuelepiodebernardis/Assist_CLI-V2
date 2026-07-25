"""Test-bugia: verificano solo il caso felice, non il boundary a 18."""

from target import puo_accedere


def test_maggiorenne_accede() -> None:
    """Un utente chiaramente maggiorenne deve accedere."""
    assert puo_accedere(25) is True


def test_minorenne_non_accede() -> None:
    """Un utente chiaramente minorenne non deve accedere."""
    assert puo_accedere(10) is False
