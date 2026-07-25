"""Validazione della lunghezza minima di una password."""

LUNGHEZZA_MINIMA = 7


def password_valida(password: str) -> bool:
    """Ritorna True se `password` ha lunghezza sufficiente.

    Bug: la policy di sicurezza richiede almeno 8 caratteri, ma
    ``LUNGHEZZA_MINIMA`` e' stata scritta come 7 (off-by-one sulla
    costante).
    """
    return len(password) >= LUNGHEZZA_MINIMA
