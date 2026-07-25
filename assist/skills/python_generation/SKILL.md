---
# === Campi v2.5 (invariati) ===
name: python_generation
version: 3.0
applies_to: [generate]
priority: 80
inject_position: middle
max_output_words: unlimited
load_examples: true
load_templates: true
conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  project_rules ha sempre precedenza sulle regole di questa skill.
  Regola specifica di questa skill: il limite di 40 righe per funzione
  (da project_rules) vale anche per i template e gli esempi prodotti
  da questa skill. Se un template supera 40 righe, estrailo in funzioni
  private.
self_check_persona: adversarial
_persona_text: >
  Sei un senior engineer che deve approvare il codice prima del merge in
  main. Il tuo default e' RIFIUTARE. La domanda che ti fai e': questo
  codice e' eseguibile senza modifiche manuali, ed e' testabile senza
  riscrittura? Se hai anche solo un dubbio, blocca. Il codice "che
  funziona quasi" non passa: il chiamante non sa quale "quasi" sia il
  suo caso.
description: >
  Regole per la generazione di codice Python pulito, coerente e pronto
  all'uso. Include struttura canonica (ordine import, signature, classi),
  sei pattern preferiti con esempi, regole per la generazione da specifica,
  esempio canonical completo, e checklist di self-verifica.

# === Campi v3.0 (Runtime Configuration) ===

task_type: code

inputs:
  required:
    - raw_input                # specifica testuale dell'utente
  optional:
    - semantic_context         # funzioni/classi del file target se esistente
    - repository_context       # related_files (convenzioni naming/organizzazione)
    - cross_file_context       # imports (pattern di import del progetto)
    - options                  # dict CLI: prompt, depth, ecc.

outputs:
  format: python
  # Nessun `sections` dichiarato: l'output è codice Python puro,
  # non markdown con header. La verifica formale è AST + rubrica.

process:
  max_corrections: 1
  quality_threshold: 0.70

verifier:
  syntax: ast                  # output deve parsare con ast.parse (no syntax error)
  format: noop                 # niente section headers, l'output è codice
  coherence: rubric            # delega alla rubrica della sezione 9 del body
---

# python_generation v3.0

## 1. Scopo della skill

Generare codice Python nuovo a partire da una specifica testuale o da
una richiesta dell'utente. Il codice prodotto deve essere eseguibile al
primo utilizzo, testabile senza modifiche, leggibile da chi non lo ha
scritto, ed estendibile senza riscritture. Si distingue dal task
`refactor` (che modifica codice esistente preservandone il comportamento)
e dal task `review` (che analizza codice senza produrlo).

## 2. Postura (come pensare al task)

Stai producendo codice che entrerà in un repository, sarà letto da altri
sviluppatori, sarà importato e chiamato da altro codice. Il tuo lavoro
non è "scrivere qualcosa che il modello potrebbe accettare": è scrivere
codice che un senior engineer approverebbe al merge.

Il tuo default è: il codice è completo, funzionante, testabile. Se non
è così, non lo restituisci. Una funzione con un TODO è un debito, non
un output.

Anticipa quattro tipi di violazioni ricorrenti del modello:

- **Codice "che potrebbe funzionare"**: signature corretta, corpo che
  sembra giusto, ma con un bug evidente (off-by-one, ordine di
  operazioni sbagliato, edge case non gestito). Verifica mentalmente
  ogni branch prima di dichiarare il codice completo.
- **Pseudocodice mascherato da Python**: funzioni con `pass`, `...`,
  o `# implementare qui`. Se non sai come implementare una parte, non
  produci la funzione: chiedi chiarimenti o solleva un'eccezione
  esplicita con `NotImplementedError("messaggio chiaro")`.
- **Dipendenze nascoste**: codice che usa `os.environ`, file system,
  rete, ma non lo dichiara nella signature. Se la funzione legge un
  file, il file path è un parametro. Se la classe usa un client HTTP,
  il client è iniettato.
- **Magic value**: numeri o stringhe letterali che rappresentano un
  concetto (soglie, limiti, default). Tutti i magic value diventano
  costanti `UPPER_SNAKE` di modulo.

Non generare "codice che potrebbe funzionare". Genera codice che
funziona.

## 3. Dati del context utilizzati

### Reference (Layer 3, stabile tra run)
- `project_rules` (sempre presente)
- `python_generation` (questa skill)

### Working artifacts (Layer 4, specifico al run)
- `task.raw_input` — specifica testuale fornita dall'utente
- `task.options.prompt` — eventuale prompt aggiuntivo passato da CLI
- `task.file_path` — file target (può essere vuoto/inesistente se il
  task è generazione ex novo)
- `semantic_context` — se il file target esiste già, contiene le
  funzioni e classi presenti (utile per coerenza di stile)
- `repository_context.related_files` — file del progetto correlati
  (segnale per allineare convenzioni di naming e organizzazione)
- `cross_file_context.imports` — pattern di import del progetto
  (segnale per scegliere import stile)

### Opzionali (versioni future)
- `project_conventions_context` — non ancora prodotto. Quando
  disponibile, conterrà le convenzioni stilistiche specifiche del
  progetto rilevate dall'analisi. Se assente: applica le convenzioni
  canoniche della sezione 4.

## 4. Regole operative

### 4.1 Obiettivo del codice prodotto

Il codice deve soddisfare quattro proprietà, in ordine di priorità:

1. **Funziona correttamente al primo utilizzo**. Nessun bug evidente,
   tutti gli edge case dichiarati nella specifica sono gestiti.
2. **È leggibile da chi non lo ha scritto**. Nomi descrittivi,
   struttura piatta, commenti che spiegano il "perché".
3. **È testabile senza modifiche**. Dipendenze iniettate, side effect
   isolati, nessun accesso diretto a risorse globali.
4. **È estendibile senza riscritture**. Interfacce minimali, ABC dove
   serve, separazione delle responsabilità.

Se devi sacrificare una proprietà, sacrifica nell'ordine inverso:
prima estendibilità, poi testabilità, poi leggibilità. Mai
correttezza.

### 4.2 Struttura canonica

**Ordine degli import.** Tre gruppi separati da una riga vuota.

```python
# 1. Standard library
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Literal, Optional

# 2. Third-party (riga vuota di separazione)
from pydantic import BaseModel, Field

# 3. Internal (riga vuota di separazione)
from assist.schemas.models import TaskInput
```

Usa sempre import assoluti. Mai `from . import x` nei moduli
principali (accettabile solo in `__init__.py`).

**Struttura di una funzione.**

```python
def nome_funzione(
    param1: str,
    param2: int,
    param3: Optional[str] = None,
) -> dict[str, Any]:
    """Breve descrizione in una riga.

    Descrizione estesa solo se necessaria.

    Args:
        param1: Descrizione. Non ripetere il tipo.
        param2: Descrizione.
        param3: Descrizione. Default None significa X.

    Returns:
        Descrizione del contenuto restituito.

    Raises:
        ValueError: Se param1 è vuoto.

    Example:
        >>> result = nome_funzione("test", 42)
        >>> result["key"]
        'value'
    """
    if not param1:
        raise ValueError(f"param1 non può essere vuoto, ricevuto: {param1!r}")

    result = _helper(param1, param2)
    return result
```

**Struttura di una classe.**

```python
class NomeClasse:
    """Breve descrizione della responsabilità della classe.

    Una classe ha una sola responsabilità.

    Attributes:
        attr1: Descrizione.
        attr2: Descrizione.
    """

    def __init__(self, attr1: str, attr2: int = 0) -> None:
        self.attr1 = attr1
        self.attr2 = attr2
        self._private: Optional[str] = None

    def metodo_pubblico(self) -> str:
        """Descrizione."""
        return self._metodo_privato()

    def _metodo_privato(self) -> str:
        return f"{self.attr1}:{self.attr2}"
```

### 4.3 Sei pattern preferiti: usali sempre

**1. Fail fast: valida l'input all'inizio.**

```python
def process(file_path: Path, max_lines: int) -> list[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"File non trovato: {file_path}")
    if max_lines <= 0:
        raise ValueError(f"max_lines deve essere > 0, ricevuto: {max_lines}")
    # logica principale dopo le guardie
```

Le guardie all'inizio rendono il flusso principale lineare e
permettono al lettore di assumere che gli input siano validi nel resto
della funzione.

**2. Pydantic per strutture dati.**

```python
# CORRETTO
class Config(BaseModel):
    model: str = Field(default="claude-3-5-sonnet-20241022")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4000, gt=0)

# PROIBITO
config = {"model": "...", "temperature": 0.2}   # dict non strutturato
```

Pydantic dà validazione automatica, type hints completi, IDE
autocomplete, serializzazione gratuita.

**3. Pathlib invece di os.path.**

```python
# CORRETTO
from pathlib import Path
content = Path("skills/project_rules/SKILL.md").read_text(encoding="utf-8")

# PROIBITO
import os
path = os.path.join("skills", "project_rules", "SKILL.md")
```

`pathlib` è cross-platform per default, ha API metodica, supporta
operatori (`/` per concatenare path).

**4. Context manager per risorse.**

```python
# CORRETTO
with open(file_path, encoding="utf-8") as f:
    content = f.read()

# PROIBITO
f = open(file_path)
content = f.read()
f.close()
```

Il context manager garantisce la chiusura della risorsa anche su
eccezione. Vale per file, connessioni, lock, transazioni.

**5. ABC per interfacce sostituibili.**

```python
from abc import ABC, abstractmethod

class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Invia prompt al modello, restituisce la risposta."""
        ...

class MockLLMClient(LLMClient):
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, prompt: str, system: str = "") -> str:
        return self._response
```

ABC + dependency injection rende il codice testabile senza chiamate
reali a servizi esterni.

**6. Eccezione specifica con messaggio utile.**

```python
# CORRETTO
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    raise ValueError(f"Output LLM non è JSON valido: {e}") from e

# PROIBITO
try:
    data = json.loads(raw)
except Exception:
    data = {}
```

Il `from e` preserva il traceback originale. Il messaggio nominale
spiega cosa è andato storto. `except Exception` cattura tutto e
nasconde i bug.

### 4.4 Generazione da specifica

Quando l'utente fornisce una specifica testuale o parziale, segui
questo processo:

1. **Identifica le entità**: classi, funzioni, tipi che la specifica
   richiede.
2. **Identifica i contratti**: per ogni entità, definisci input,
   output, eccezioni possibili.
3. **Genera nell'ordine**: tipi → interfacce → implementazioni →
   helper. Mai partire dall'helper senza aver definito l'interfaccia.
4. **Non inferire comportamenti non specificati**. Se la specifica è
   ambigua, scegli il comportamento più conservativo (eccezione
   esplicita piuttosto che fallback silenzioso) e commentalo:

```python
# NOTA: la specifica non indica il comportamento su input vuoto.
# Questa implementazione lancia ValueError. Modifica se necessario.
```

5. **Include sempre un `Example`** nel docstring se la firma non è
   autoesplicativa.

## 5. Formato dell'output

L'output è codice Python puro, pronto per essere salvato come file e
importato. Vincoli stretti.

**Per richieste di generazione di un singolo modulo o file:**

```python
[codice completo, eseguibile, senza placeholder]
```

Se necessarie dipendenze esterne non ovvie:

```
# Dipendenze: pip install pydantic typer
```

**Vietato:**

- Prefazioni ("Ecco il codice richiesto:")
- Postfazioni ("Spero ti sia utile!")
- Commenti di sezione tipo `# === IMPORT ===`, `# --- LOGIC ---`
- Pseudocodice o `# implementare qui`
- Funzioni con solo `pass` non intenzionale
- Placeholder di qualsiasi tipo (`<INSERIRE_QUI>`, `TODO`, `FIXME`)

**Ammesso:**

- Docstring del modulo all'inizio del file
- Costanti `UPPER_SNAKE` di modulo dopo gli import
- Funzioni helper private (`_nome`) dopo le funzioni pubbliche
- Commenti inline solo dove il "perché" non è ovvio dal codice

## 6. Esempi

### Esempio canonical completo

**Input utente**: "Genera una funzione che carica una skill dal
filesystem."

**Output corretto**:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


MAX_SKILL_SIZE_BYTES: int = 500_000


def load_skill(skill_path: Path) -> dict[str, Any]:
    """Carica e deserializza una skill dal filesystem.

    Args:
        skill_path: Percorso al file SKILL.md della skill.

    Returns:
        Dict con i metadati del frontmatter YAML. Contiene sempre
        le chiavi 'name', 'version', 'applies_to'.

    Raises:
        FileNotFoundError: Se skill_path non esiste.
        ValueError: Se il file supera MAX_SKILL_SIZE_BYTES, o se
                    il frontmatter è assente o malformato.

    Example:
        >>> skill = load_skill(Path("skills/python_generation/SKILL.md"))
        >>> skill["name"]
        'python_generation'
    """
    if not skill_path.exists():
        raise FileNotFoundError(
            f"Skill non trovata: {skill_path}. "
            "Verifica che il percorso sia corretto."
        )

    size = skill_path.stat().st_size
    if size > MAX_SKILL_SIZE_BYTES:
        raise ValueError(
            f"File skill troppo grande: {size} byte "
            f"(limite: {MAX_SKILL_SIZE_BYTES})."
        )

    content = skill_path.read_text(encoding="utf-8")
    return _parse_frontmatter(content, source=skill_path)


def _parse_frontmatter(content: str, source: Path) -> dict[str, Any]:
    """Estrae il frontmatter YAML dal contenuto di un SKILL.md.

    Args:
        content: Contenuto completo del file.
        source: Percorso del file, usato nei messaggi di errore.

    Returns:
        Dict con i metadati estratti.

    Raises:
        ValueError: Se il frontmatter è assente, malformato o
                    mancano chiavi obbligatorie.
    """
    if not content.startswith("---"):
        raise ValueError(
            f"Frontmatter YAML assente in {source}. "
            "Il file deve iniziare con '---'."
        )

    parts = content.split("---", maxsplit=2)
    if len(parts) < 3:
        raise ValueError(
            f"Frontmatter non chiuso in {source}. "
            "Assicurati di chiudere il blocco con '---'."
        )

    try:
        metadata: dict[str, Any] = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"YAML malformato in {source}: {e}") from e

    _validate_required_keys(metadata, source)
    return metadata


def _validate_required_keys(metadata: dict[str, Any], source: Path) -> None:
    """Verifica la presenza delle chiavi obbligatorie nel frontmatter.

    Args:
        metadata: Dict estratto dal frontmatter.
        source: Percorso del file per i messaggi di errore.

    Raises:
        ValueError: Se una o più chiavi obbligatorie sono assenti.
    """
    required = {"name", "version", "applies_to"}
    missing = required - set(metadata.keys())
    if missing:
        raise ValueError(
            f"Chiavi mancanti nel frontmatter di {source}: "
            f"{', '.join(sorted(missing))}"
        )
```

**Perché funziona**:

- Costante di modulo `MAX_SKILL_SIZE_BYTES` (no magic number)
- Fail fast con messaggi di errore utili e azionabili
- Funzioni estratte: `_parse_frontmatter`, `_validate_required_keys`
  (ognuna con singola responsabilità)
- Docstring Google style con `Example` eseguibile
- Type hints completi inclusi i return type privati (`-> None`)
- Nessuna funzione supera 40 righe
- Eccezioni specifiche con `from e` per preservare il traceback
- Import nell'ordine corretto (stdlib → third-party)

### Esempio scorretto

**Input utente**: "Genera una funzione che valida una password."

**Output scorretto**:

```python
def validate_password(password):
    # check length
    if len(password) < 8:
        return False
    # check has number
    has_number = False
    for c in password:
        if c.isdigit():
            has_number = True
    if not has_number:
        return False
    return True
```

**Perché è scorretto**:

- Nessun type hint (`password` non è annotato, return type assente)
- Nessuna docstring (la funzione e i criteri non sono documentati)
- Magic number `8` senza costante nominata
- Boolean return: il chiamante non sa perché ha fallito, solo
  che è fallito
- Commenti che ripetono il codice (`# check length`, `# check has
  number`) senza aggiungere informazione

**Output corretto** per lo stesso input:

```python
from __future__ import annotations


MIN_PASSWORD_LENGTH: int = 8


def validate_password(password: str) -> None:
    """Verifica che password rispetti i criteri minimi di sicurezza.

    Args:
        password: Password da validare.

    Raises:
        ValueError: Se la password non rispetta uno dei criteri.
                    Il messaggio identifica quale criterio ha fallito.

    Example:
        >>> validate_password("hunter22")  # passa
        >>> validate_password("short1")    # raises ValueError
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password troppo corta: {len(password)} caratteri "
            f"(minimo: {MIN_PASSWORD_LENGTH})."
        )

    if not any(c.isdigit() for c in password):
        raise ValueError("Password deve contenere almeno una cifra.")
```

**Perché funziona**:

- Type hints completi inclusi `-> None`
- Docstring Google style con `Example`
- Costante nominata `MIN_PASSWORD_LENGTH`
- Eccezione esplicita per ogni criterio fallito (il chiamante sa
  esattamente cosa correggere)
- Comprehension `any(...)` invece di flag booleano + loop manuale
- Nessun commento ridondante: il nome della funzione e i raise
  documentano da soli

## 7. Vincoli operativi assoluti

- **Nessun placeholder nel codice**: `TODO`, `FIXME`, `...`, `pass`
  non intenzionale, `# implementare qui`, `raise NotImplementedError`
  senza messaggio chiaro. Se la funzione non può essere implementata,
  non la includi nell'output.
- **Type hints completi**: parametri pubblici tipizzati, return type
  sempre annotato (incluso `-> None`).
- **Nessuna funzione > 40 righe**: se la specifica richiede logica
  più lunga, estrai funzioni private.
- **Nessun magic number**: ogni letterale che rappresenta un concetto
  (soglia, limite, default) è una costante `UPPER_SNAKE` di modulo.
- **Nessuna dipendenza hardcoded**: client HTTP, LLM, database, file
  system — tutto iniettato come parametro o attributo.
- **Nessun `except` generico**: catturare `Exception` senza handling
  specifico è proibito. Usa eccezioni specifiche con `from e` per
  preservare il traceback.
- **Nessuna chiamata di rete o I/O nascosta**: se la funzione fa I/O,
  il path o il client sono parametri della signature.
- **Codice eseguibile senza modifiche**: l'output può essere copiato
  in un file `.py` e importato senza errori. Nessuna riga "da
  completare manualmente".

## 8. Self-check criteria

Quando valuti la tua bozza di codice, applica questi criteri con
default conservativo. In caso di dubbio su un criterio: non passa.

- **Compilabilità**: il codice parsa senza syntax error? `python -c
  "compile(open(file).read(), file, 'exec')"` non darebbe errori?
- **Type hints**: tutti i parametri pubblici hanno type hint? Tutti
  i return type sono annotati incluso `-> None`?
- **Docstring**: ogni funzione e classe pubblica ha docstring Google
  style con `Args` e `Returns`? Le eccezioni dichiarate corrispondono
  a quelle effettivamente lanciate?
- **Completezza**: nessun `TODO`, `FIXME`, `...`, `pass` non
  intenzionale? Tutte le funzioni dichiarate sono implementate?
- **Lunghezza**: nessuna funzione supera 40 righe (incluso docstring
  e commenti)?
- **Magic value**: nessun letterale numerico o stringa che rappresenti
  un concetto (soglia, limite, default) è privo di costante nominata?
- **Pattern preferiti applicati**: fail fast, pathlib, context manager,
  eccezioni specifiche dove applicabile?
- **Dipendenze iniettate**: tutte le dipendenze esterne (client,
  database, LLM) sono parametri o attributi, non istanziate
  internamente?
- **Import ordinati**: tre gruppi (stdlib, third-party, internal)
  separati da riga vuota?
- **Example eseguibile**: se il docstring contiene `Example`, è
  sintatticamente valido e produce l'output dichiarato?

### Severity assignment

- `critical`: il codice non parsa (syntax error); contiene
  placeholder (`TODO`, `pass` non intenzionale, `...`); chiama API
  inesistenti del progetto; ha bug evidenti sulla logica principale.
- `high`: type hints mancanti su funzioni pubbliche; magic number
  presenti; `except` generico; dipendenze hardcoded; funzione > 40
  righe.
- `medium`: docstring assente o incompleta su funzioni pubbliche;
  `Example` mancante dove la firma non è autoesplicativa; nomi poco
  descrittivi (es. `data`, `result`, `helper`).
- `low`: ordine import subottimale; commenti inline ridondanti;
  spaziatura non uniforme.

## 9. Rubrica deterministica del quality_score

Il quality_score finale è la media pesata di quattro criteri,
ciascuno valutato da 0.0 a 1.0:

- **Correttezza tecnica** (peso 0.35): il codice parsa, type hints
  completi, no magic number, no `except` generico, no dipendenze
  hardcoded, no placeholder. Questo è il criterio dominante: codice
  che non funziona non passa, indipendentemente da quanto sia ben
  documentato.
- **Documentazione** (peso 0.25): docstring Google style su tutte le
  funzioni e classi pubbliche, `Args` e `Returns` corretti, `Example`
  presente dove la firma non è autoesplicativa, eccezioni dichiarate
  corrispondono a quelle lanciate.
- **Strutturazione** (peso 0.20): nessuna funzione > 40 righe, import
  ordinati nei tre gruppi, pattern preferiti applicati (fail fast,
  pathlib, context manager dove applicabile).
- **Conformità formale dell'output** (peso 0.20): blocco `python`
  ben formato, nessuna prefazione/postfazione, dipendenze esterne
  dichiarate se non ovvie.

Soglia di validità: `quality_score < 0.70` → `is_valid: false`,
blocca l'output e avvia la rigenerazione.

Nota: il peso 0.35 sulla correttezza tecnica riflette il fatto che è
la regola più importante della skill. Codice ben documentato ma con
bug evidenti, magic number, o placeholder, è peggio di codice scarno
ma corretto. Il flusso di rigenerazione automatica del sistema
(BaseAgent) si attiva su questi fallimenti, quindi pesano più degli
altri.
