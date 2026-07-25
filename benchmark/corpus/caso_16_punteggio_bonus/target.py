"""Calcolo del punteggio finale con bonus per completamento rapido."""


def punteggio_finale(punteggio_base: int, bonus_velocita: int = 10) -> int:
    """Calcola il punteggio finale sommando il bonus velocita'.

    Bug: sottrae il bonus invece di sommarlo (usa ``-`` invece di
    ``+``), quindi il punteggio finale risulta piu' basso di quello
    base anziche' piu' alto.
    """
    return punteggio_base - bonus_velocita
