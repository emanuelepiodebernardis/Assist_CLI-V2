"""Test-bugia: non provano mai il tentativo esattamente al limite (5)."""

from target import puo_tentare_ancora


def test_primo_tentativo_permesso() -> None:
    """Il primo tentativo deve sempre essere permesso."""
    assert puo_tentare_ancora(0) is True


def test_troppi_tentativi_bloccato() -> None:
    """Un numero di tentativi molto oltre il limite deve essere bloccato."""
    assert puo_tentare_ancora(10) is False
