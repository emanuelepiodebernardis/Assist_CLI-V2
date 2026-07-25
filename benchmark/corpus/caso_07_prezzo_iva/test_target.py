"""Test-bugia: controllano solo segno e tipo, non il valore esatto."""

from target import prezzo_con_iva


def test_prezzo_con_iva_e_positivo() -> None:
    """Il prezzo finale deve essere un numero positivo."""
    assert prezzo_con_iva(100) > 0


def test_prezzo_con_iva_e_float() -> None:
    """Il prezzo finale deve essere un float."""
    assert isinstance(prezzo_con_iva(50), float)
