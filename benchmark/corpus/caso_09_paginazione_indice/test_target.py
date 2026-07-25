"""Test-bugia: controllano solo la distanza relativa tra pagine
consecutive e la divisibilita' per `per_pagina`, mai il valore
assoluto (che rivelerebbe lo spostamento)."""

from target import indice_iniziale_pagina


def test_pagine_consecutive_distano_di_una_pagina() -> None:
    """Tra due pagine consecutive la distanza deve essere `per_pagina`."""
    assert indice_iniziale_pagina(3, 10) - indice_iniziale_pagina(2, 10) == 10


def test_indice_e_multiplo_di_per_pagina() -> None:
    """L'indice iniziale deve sempre essere un multiplo di `per_pagina`."""
    assert indice_iniziale_pagina(5, 20) % 20 == 0
