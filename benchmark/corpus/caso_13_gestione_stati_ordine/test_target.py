"""Test-bugia: verificano solo il cambio di stato, mai il contenuto
dello storico eventi."""

from target import Ordine


def test_spedisci_cambia_stato() -> None:
    ordine = Ordine()
    ordine.spedisci()
    assert ordine.stato == "spedito"


def test_spedisci_non_solleva_eccezioni() -> None:
    ordine = Ordine()
    ordine.spedisci()
    assert ordine.stato is not None
