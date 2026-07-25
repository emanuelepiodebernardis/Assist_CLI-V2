"""Calcolo del prezzo finale (lordo) applicando l'IVA."""


def prezzo_con_iva(prezzo_netto: float, aliquota: float = 0.22) -> float:
    """Calcola il prezzo lordo applicando l'aliquota IVA a
    `prezzo_netto`.

    Bug: sottrae l'IVA invece di sommarla (usa ``-`` invece di
    ``+``), quindi il prezzo finale risulta piu' basso di quello
    netto anziche' piu' alto.
    """
    return prezzo_netto - (prezzo_netto * aliquota)
