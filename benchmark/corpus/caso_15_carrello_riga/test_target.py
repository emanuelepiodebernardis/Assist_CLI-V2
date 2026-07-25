"""Test-bugia: non provano mai una quantita' non positiva."""

from target import totale_riga


def test_totale_riga_con_quantita_positiva() -> None:
    assert totale_riga(10.0, 3) == 30.0


def test_totale_riga_quantita_uno() -> None:
    assert totale_riga(5.5, 1) == 5.5
