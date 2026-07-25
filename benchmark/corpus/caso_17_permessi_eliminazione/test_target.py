"""Test-bugia: provano solo i casi "tutto vero" e "tutto falso", mai
la combinazione mista che rivelerebbe l'errore."""

from target import puo_eliminare_risorsa


def test_admin_proprietario_puo_eliminare() -> None:
    assert puo_eliminare_risorsa(True, True) is True


def test_utente_normale_non_puo_eliminare() -> None:
    assert puo_eliminare_risorsa(False, False) is False
