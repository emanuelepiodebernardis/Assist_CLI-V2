"""Calcolo dell'indice (0-based) del primo elemento di una pagina."""


def indice_iniziale_pagina(pagina: int, per_pagina: int) -> int:
    """Ritorna l'indice del primo elemento della pagina richiesta.

    `pagina` e' 1-based (la prima pagina e' 1). Bug: usa
    ``pagina + 1`` invece di ``pagina - 1`` per convertire a 0-based,
    quindi l'indice iniziale risulta spostato di due pagine intere.
    """
    return (pagina + 1) * per_pagina
