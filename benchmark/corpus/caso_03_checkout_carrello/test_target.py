"""Test-bugia: non provano mai la combinazione mista (un solo requisito)."""

from target import puo_fare_checkout


def test_checkout_con_entrambi_validi() -> None:
    """Con carrello pieno e pagamento valido si deve poter procedere."""
    assert puo_fare_checkout(True, True) is True


def test_checkout_senza_nulla() -> None:
    """Senza carrello ne' pagamento non si deve poter procedere."""
    assert puo_fare_checkout(False, False) is False
