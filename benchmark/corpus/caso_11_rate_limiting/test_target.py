"""Test-bugia: provano solo i casi "tutto sotto" e "tutto sopra",
mai la combinazione mista che rivelerebbe l'errore."""

from target import richiesta_consentita


def test_entrambi_sotto_limite_consentita() -> None:
    assert richiesta_consentita(5, 50) is True


def test_entrambi_sopra_limite_bloccata() -> None:
    assert richiesta_consentita(20, 200) is False
