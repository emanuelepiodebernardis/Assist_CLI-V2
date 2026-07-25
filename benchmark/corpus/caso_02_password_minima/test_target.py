"""Test-bugia: non controllano il valore esatto della soglia (7 o 8)."""

from target import password_valida


def test_password_lunga_e_valida() -> None:
    """Una password chiaramente lunga deve essere valida."""
    assert password_valida("supersegreta123") is True


def test_password_troppo_corta() -> None:
    """Una password chiaramente corta deve essere non valida."""
    assert password_valida("abc") is False
