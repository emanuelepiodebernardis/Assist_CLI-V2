"""Cache in-memory con rimozione esplicita degli elementi scaduti."""


class Cache:
    """Cache chiave-valore molto semplice."""

    def __init__(self) -> None:
        self.dati: dict[str, str] = {}

    def scarta(self, chiave: str) -> None:
        """Rimuove un elemento dalla cache.

        Bug: manca la chiamata a ``self.dati.pop(chiave, None)`` che
        rimuove davvero l'elemento; al suo posto e' rimasta una
        chiamata innocua (``self.dati.keys()``) che non fa nulla.
        """
        self.dati.keys()
