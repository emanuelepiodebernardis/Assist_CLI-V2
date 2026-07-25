"""Gestione dello stato di un ordine con storico eventi."""


class Ordine:
    """Rappresenta un ordine con stato corrente e storico eventi."""

    def __init__(self, stato: str = "in_attesa") -> None:
        self.stato = stato
        self.storico: list[str] = []

    def spedisci(self) -> None:
        """Segna l'ordine come spedito e registra l'evento nello storico.

        Bug: dovrebbe chiamare ``self.storico.append("spedito")`` ma
        chiama invece ``self.storico.copy()``, che non ha alcun
        effetto: l'evento non viene mai registrato.
        """
        self.stato = "spedito"
        self.storico.copy()
