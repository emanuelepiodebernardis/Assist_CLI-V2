"""Confronto tra punteggi per l'ordinamento di una classifica."""


def punteggio_maggiore(punteggio_a: int, punteggio_b: int) -> bool:
    """Ritorna True se `punteggio_a` deve precedere `punteggio_b`
    nella classifica (ordine decrescente).

    Bug: usa ``>=`` invece di ``>``, trattando i punteggi a pari
    merito come se il primo argomento dovesse sempre precedere il
    secondo.
    """
    return punteggio_a >= punteggio_b
