"""Client nullo per la modalita' evidence-only (--provider none).

Il Proof Engine funziona anche SENZA alcun LLM: il verdetto e'
deciso dalle evidenze deterministiche (test esistenti, mutation
testing, coverage). Senza modello mancano solo le parti accessorie:
generazione di test boundary/property, spiegazione e fix proposto.
"""

from assist.llm.base import LLMClient


class NullLLMClient(LLMClient):
    """Ritorna sempre stringa vuota: nessuna chiamata, nessun costo."""

    def complete(
        self,
        prompt: str,
        system: str = "",
    ) -> str:
        return ""
