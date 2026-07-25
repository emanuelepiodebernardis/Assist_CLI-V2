"""Test-bugia: passano sempre `soglia_anni` esplicita, non usano mai
il default della funzione."""

from target import sconto_fedelta


def test_sconto_con_soglia_esplicita_superata() -> None:
    assert sconto_fedelta(6, soglia_anni=5) == 0.05


def test_sconto_con_soglia_esplicita_non_raggiunta() -> None:
    assert sconto_fedelta(2, soglia_anni=5) == 0.0
