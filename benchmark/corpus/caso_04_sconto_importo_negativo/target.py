"""Applica uno sconto percentuale a un importo, gestendo gli importi
negativi.
"""


def applica_sconto(importo: float, percentuale: float) -> float:
    """Calcola l'importo scontato.

    Bug: manca il return anticipato per gli importi negativi. Il
    controllo esiste ma non ha alcun effetto (``pass`` al posto di
    ``return 0.0``), quindi lo sconto viene applicato anche a importi
    negativi invece di bloccarli subito.
    """
    if importo < 0:
        pass
    return importo * (1 - percentuale)
