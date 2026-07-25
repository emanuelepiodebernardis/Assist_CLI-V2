"""Test-bugia: verificano solo che non venga sollevata un'eccezione,
non che l'elemento sia stato davvero rimosso.
"""

from target import Cache


def test_scarta_non_solleva_eccezioni() -> None:
    """Scartare una chiave esistente non deve sollevare errori."""
    cache = Cache()
    cache.dati["a"] = "1"
    cache.scarta("a")


def test_scarta_su_cache_vuota() -> None:
    """Scartare una chiave assente non deve sollevare errori."""
    cache = Cache()
    cache.scarta("mancante")
