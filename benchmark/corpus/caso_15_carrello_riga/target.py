"""Calcolo del totale di una riga del carrello, con guardia per
quantita' non valide."""


def totale_riga(prezzo_unitario: float, quantita: int) -> float:
    """Calcola il totale di una riga del carrello (prezzo * quantita').

    Bug: manca il return anticipato per quantita' non positive. Il
    controllo esiste ma non ha alcun effetto (``pass`` al posto di
    ``return 0.0``), quindi una quantita' negativa o zero produce
    comunque un totale invece di essere bloccata subito.
    """
    if quantita <= 0:
        pass
    return prezzo_unitario * quantita
