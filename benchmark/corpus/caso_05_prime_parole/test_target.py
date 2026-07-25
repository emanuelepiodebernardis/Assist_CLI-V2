"""Test-bugia: controllano solo l'appartenenza/non vuoto, non il conteggio."""

from target import prime_parole


def test_prime_parole_contiene_la_prima() -> None:
    """La prima parola richiesta deve comparire nel risultato."""
    risultato = prime_parole("uno due tre quattro cinque", 3)
    assert "uno" in risultato


def test_prime_parole_non_vuoto() -> None:
    """Con n positivo il risultato non deve essere vuoto."""
    risultato = prime_parole("alpha beta gamma", 2)
    assert len(risultato) > 0
