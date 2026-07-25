# Esempio refactoring: da monolite a moduli separati
# Questo file mostra un caso reale di refactoring applicato
# al pattern "god function" con dipendenze hardcoded.

# ─────────────────────────────────────────────────────────────
# PRIMA — funzione monolitica, non testabile, dipendenze nascoste
# ─────────────────────────────────────────────────────────────

class AgentV1:
    def run(self, command, file_path, verbose=False):
        import anthropic
        client = anthropic.Anthropic()

        # leggi file
        try:
            with open(file_path) as f:
                code = f.read()
        except:
            print("Errore lettura file")
            return None

        # costruisci prompt
        if command == "review":
            prompt = f"Review this code:\n{code}"
        elif command == "explain":
            prompt = f"Explain this code:\n{code}"
        else:
            prompt = f"Process this code:\n{code}"

        if verbose:
            print(f"Sending prompt ({len(prompt)} chars)...")

        # chiama modello
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text

        if verbose:
            print(f"Got response ({len(result)} chars)")

        return result


# ─────────────────────────────────────────────────────────────
# DOPO — moduli separati, testabile, dipendenze iniettate
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


# ── Contratto LLM ─────────────────────────────────────────────
class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str: ...


# ── Lettura file isolata ───────────────────────────────────────
def read_source_file(file_path: Path) -> str:
    """Legge un file sorgente con gestione esplicita degli errori.

    Args:
        file_path: Percorso del file da leggere.

    Returns:
        Contenuto del file come stringa.

    Raises:
        FileNotFoundError: Se il file non esiste.
        PermissionError: Se il file non è leggibile.
        UnicodeDecodeError: Se il file non è UTF-8 valido.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File non trovato: {file_path}")
    return file_path.read_text(encoding="utf-8")


# ── Costruzione prompt separata dalla logica ──────────────────
PROMPT_TEMPLATES: dict[str, str] = {
    "review": "Analizza il seguente codice Python e produci una review strutturata:\n\n<code>\n{code}\n</code>",
    "explain": "Spiega il seguente codice Python in modo chiaro e sintetico:\n\n<code>\n{code}\n</code>",
}

DEFAULT_PROMPT_TEMPLATE: str = "Processa il seguente codice:\n\n<code>\n{code}\n</code>"


def build_prompt(command: str, code: str) -> str:
    """Costruisce il prompt per il modello dato il comando e il codice.

    Args:
        command: Tipo di task (review, explain, ...).
        code: Codice sorgente da includere nel prompt.

    Returns:
        Prompt completo pronto per il modello.
    """
    template = PROMPT_TEMPLATES.get(command, DEFAULT_PROMPT_TEMPLATE)
    return template.format(code=code)


# ── Agente testabile ───────────────────────────────────────────
class AgentV2:
    """Agente refactorizzato con dipendenze iniettate.

    Differenze rispetto a V1:
    - LLMClient iniettato: sostituibile con mock nei test
    - Lettura file separata: testabile in isolamento
    - Costruzione prompt separata: testabile in isolamento
    - Nessun side effect nascosto (print rimossi)
    - Type hints completi
    - Gestione errori esplicita, non silente

    Attributes:
        llm: Client LLM iniettato esternamente.
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, command: str, file_path: Path) -> str:
        """Esegue il task sul file indicato.

        Args:
            command: Tipo di task ('review', 'explain').
            file_path: Percorso del file sorgente.

        Returns:
            Output del modello come stringa.

        Raises:
            FileNotFoundError: Se il file non esiste.
            ValueError: Se il comando non è riconosciuto.
        """
        if command not in PROMPT_TEMPLATES:
            raise ValueError(
                f"Comando non riconosciuto: '{command}'. "
                f"Disponibili: {list(PROMPT_TEMPLATES.keys())}"
            )

        code = read_source_file(file_path)
        prompt = build_prompt(command, code)
        return self.llm.complete(prompt)


# ── Modifiche applicate ────────────────────────────────────────
# 1. Dependency injection: LLMClient non è più hardcoded
# 2. Extract method: read_source_file(), build_prompt() separati
# 3. Magic string → dizionario PROMPT_TEMPLATES con costanti
# 4. Guard clause: validazione comando all'inizio di run()
# 5. Eccezione generica rimossa: ogni errore ha tipo specifico
# 6. Side effect nascosti rimossi: nessun print() nel core
#
# Comportamento invariato:
# - review → prompt di review
# - explain → prompt di explain
# - altro → prompt di default (ora con ValueError esplicito)
#
# NOTA BUG: V1 restituiva None su FileNotFoundError invece di
# propagare l'eccezione. V2 propaga correttamente. Questo è
# un cambio di comportamento intenzionale e documentato.
