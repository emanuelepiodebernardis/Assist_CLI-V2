"""Test-bugia: non provano mai un indirizzo con spazi iniziali o
finali (il caso che rivelerebbe la normalizzazione mancante)."""

from target import email_valida


def test_email_valida_senza_spazi() -> None:
    assert email_valida("utente@example.com") is True


def test_email_senza_chiocciola_non_valida() -> None:
    assert email_valida("non-una-email.com") is False
