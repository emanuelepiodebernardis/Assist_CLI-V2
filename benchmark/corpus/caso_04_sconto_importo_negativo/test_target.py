"""Test-bugia: non provano mai un importo negativo."""

from target import applica_sconto


def test_sconto_su_importo_positivo() -> None:
    """Uno sconto del 10% su 100 deve dare 90."""
    assert applica_sconto(100, 0.1) == 90.0


def test_nessuno_sconto() -> None:
    """Con percentuale 0 l'importo deve restare invariato."""
    assert applica_sconto(50, 0.0) == 50.0
