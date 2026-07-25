"""Estrazione delle prime N parole di un testo."""


def prime_parole(testo: str, n: int) -> list[str]:
    """Ritorna le prime `n` parole di `testo`.

    Bug: lo slice usa ``n - 1`` come limite superiore invece di
    ``n``, escludendo sempre l'ultima parola richiesta.
    """
    parole = testo.split()
    return parole[:n - 1]
