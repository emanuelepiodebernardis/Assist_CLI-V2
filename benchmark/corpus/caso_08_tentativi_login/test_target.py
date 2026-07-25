"""Test-bugia: passano sempre `limite` esplicito, non usano mai il
default della funzione.
"""

from target import tentativi_rimanenti


def test_tentativi_rimanenti_con_limite_esplicito() -> None:
    """Con limite esplicito il conteggio deve essere corretto."""
    assert tentativi_rimanenti(2, limite=5) == 3


def test_tentativi_esauriti() -> None:
    """Oltre il limite esplicito i tentativi rimanenti sono zero."""
    assert tentativi_rimanenti(10, limite=5) == 0
