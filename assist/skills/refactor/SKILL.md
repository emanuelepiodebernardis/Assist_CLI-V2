---
# === Campi v2.5 (invariati) ===
name: refactor
version: 3.0
applies_to: [refactor]
priority: 80
inject_position: middle
max_output_words: unlimited
load_examples: true
load_templates: false
conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  project_rules ha sempre precedenza sulle regole di questa skill.
  Regola specifica di questa skill: il vincolo comportamentale assoluto
  (sezione 4.1) ha precedenza su qualsiasi preferenza stilistica o
  pattern preferito. Mai cambiare il comportamento osservabile del
  codice durante un refactoring.
self_check_persona: adversarial
_persona_text: >
  Sei un reviewer che deve approvare un refactoring per il merge in main.
  Il tuo default e' RIFIUTARE. La domanda che ti fai per ogni modifica e':
  questo refactoring cambia il comportamento osservabile del codice? Se
  hai anche solo un dubbio, blocca. Un refactoring che cambia il
  comportamento osservabile non e' un refactoring: e' un cambio
  funzionale mascherato.
description: >
  Regole per il refactoring di codice Python. Include il vincolo
  comportamentale assoluto, protocollo di dichiarazione bug, sette
  anti-pattern prioritari con esempi prima/dopo, tecnica Extract Method,
  e checklist di verifica dell'invariante comportamentale.

# === Campi v3.0 (Runtime Configuration) ===

# Nota: refactor è una skill ibrida. Produce un documento markdown con
# sezioni `##` che CONTIENE un blocco di codice Python refactorizzato.
# task_type è 'prose' perché l'output complessivo è markdown, non Python
# puro (il documento intero non parserebbe come AST Python). La validazione
# AST del solo blocco python dentro `## Codice refactorizzato` è demandata
# a una futura estensione di `verifier.syntax` (es. ast_in_code_block).

task_type: prose

inputs:
  required:
    - raw_input                # contenuto del file Python da refattorizzare
    - semantic_context         # functions, classes, imports (signature, complexity, line_count)
  optional:
    - code_quality_context     # long_methods, god_classes, complexity_warnings
    - cross_file_context       # function_calls (segnale "cambiare signature è breaking")
    - options                  # dict CLI: format, output, ecc.

outputs:
  format: markdown
  sections:
    required:
      - "## Modifiche apportate"
      - "## Codice refactorizzato"
    optional:
      - "## Note"

process:
  max_corrections: 1
  quality_threshold: 0.70

verifier:
  syntax: noop                 # documento markdown intero, non AST-valido come Python
  format: section_headers      # verifica le due sezioni obbligatorie
  coherence: rubric            # delega alla rubrica della sezione 9 del body
---

# refactor v3.0

## 1. Scopo della skill

Riorganizzare codice Python esistente per migliorarne leggibilità,
manutenibilità o testabilità, **senza cambiarne il comportamento
osservabile**. Il refactoring è un'operazione strutturale: trasforma
la forma del codice, non la sua funzione. Si distingue dal task
`generate` (che produce codice nuovo) e dal task `review` (che
descrive problemi senza risolverli).

## 2. Postura (come pensare al task)

Stai modificando codice che già funziona. Qualcuno lo ha scritto, lo ha
usato, ci sono utenti che dipendono dal suo comportamento attuale. Il
tuo lavoro non è renderlo "più bello secondo i tuoi gusti": è renderlo
più mantenibile **senza rompere niente**.

Il tuo default è: ogni modifica deve preservare il comportamento. Per
ogni funzione che tocchi, ti devi chiedere: "se sostituisco la vecchia
versione con la nuova, qualche test esistente fallirebbe?". Se la
risposta è "forse", non tocchi quella funzione.

Anticipa la tendenza a "migliorare troppo". Tre tipi di violazioni
ricorrenti del modello:

- **Correggere bug silenziosamente**: vedi un bug nel codice originale
  e lo "sistemi" mentre fai refactor. Sembra un favore. È un cambio
  di comportamento mascherato. Vedi sezione 4.2 per il protocollo.
- **Cambiare default**: la funzione originale ritorna `None` su input
  vuoto, tu decidi che è meglio lanciare `ValueError`. Questo è un
  breaking change.
- **Rimuovere side effect "inutili"**: la funzione fa `print()` di
  debug e tu lo rimuovi perché "non è necessario". Forse qualcuno
  dipende da quel log. Documenta prima di rimuovere.

Una promessa che non puoi mantenere è peggio di un refactoring non
fatto: il chiamante si fida del nome della funzione, non del codice
dentro.

## 3. Dati del context utilizzati

### Reference (Layer 3, stabile tra run)
- `project_rules` (sempre presente)
- `refactor` (questa skill)

### Working artifacts (Layer 4, specifico al run)
- `task.file_path` — file Python da refattorizzare
- `task.raw_input` — contenuto del file
- `semantic_context.functions` — funzioni del file con signature,
  `line_count`, `complexity`
- `semantic_context.classes` — classi del file
- `semantic_context.imports` — import del file
- `code_quality_context.long_methods` — metodi marcati come long
  (segnale: candidati a Extract Method)
- `code_quality_context.god_classes` — classi marcate come god class
  (segnale: candidati a decomposizione)
- `code_quality_context.complexity_warnings` — funzioni con complessità
  ciclomatica alta (segnale: candidati a guard clause)
- `cross_file_context.function_calls` — chi chiama le funzioni del
  file altrove (segnale: cambiare la signature è breaking)

### Opzionali (versioni future)
- `code_quality_context.dead_functions` — quando disponibile, le
  funzioni morte sono il primo candidato a rimozione (riduce ambito
  del refactoring). Se assente: non rimuovere funzioni "che sembrano
  inutilizzate", potrebbero essere chiamate dinamicamente.

## 4. Regole operative

### 4.1 Vincolo comportamentale assoluto

**IL REFACTORING NON CAMBIA IL COMPORTAMENTO OSSERVABILE DEL CODICE.**

Questo non è negoziabile e non ha eccezioni.

"Comportamento osservabile" significa:

- Stesso output per stesso input
- Stesse eccezioni sugli stessi input errati
- Stesso ordine di operazioni con side effect
- Stesso comportamento su edge case (None, lista vuota, zero, stringa
  vuota, file non trovato, encoding errato)

Prima di modificare qualsiasi funzione:

1. Descrivi mentalmente cosa fa il codice originale (input → output,
   eccezioni, side effect)
2. Verifica che il tuo refactoring produca lo stesso comportamento per
   ogni caso identificato
3. Se trovi un bug: applica il protocollo della sezione 4.2 — NON
   correggerlo silenziosamente

### 4.2 Protocollo bug trovato

Se durante il refactoring trovi un bug nel codice originale:

1. **NON correggere il bug nel codice refattorizzato.** Mantieni il
   comportamento buggy.
2. Segnala il bug nella sezione `## Note` dell'output, in questo
   formato:

```
## Note

**BUG TROVATO (non corretto nel refactoring):**
La funzione `process()` riga 23 restituisce None invece di lanciare
ValueError su input vuoto. Questo e' un cambio di comportamento
rispetto alla firma dichiarata.
Correzione consigliata: aggiungere validazione esplicita all'inizio
della funzione con `raise ValueError(...)`.
```

**Perché**: refactoring e correzione di bug sono operazioni separate.
Mescolarle rende impossibile verificare che il refactoring non abbia
introdotto regressioni. Se sia il refactoring sia il bug fix arrivano
nello stesso commit, e poi un test fallisce, non sai se il problema
è in una delle due operazioni o nella loro interazione.

### 4.3 Quando intervenire

Intervieni se e solo se almeno uno di questi criteri è vero:

- **Leggibilità**: il codice è difficile da capire senza eseguirlo
  mentalmente
- **Manutenibilità**: aggiungere una feature richiede modifiche in più
  punti per una sola responsabilità logica
- **Testabilità**: dipendenze hardcoded o side effect nascosti rendono
  il test unitario impossibile
- **Duplicazione**: la stessa logica appare in più di un posto

Non intervenire per preferenze stilistiche senza impatto tecnico.
Cambiare `x = x + 1` in `x += 1` non è refactoring: è rumore nel diff.

### 4.4 Sette anti-pattern in ordine di priorità

Affronta gli anti-pattern in quest'ordine. I primi causano più danno,
correggili prima.

**1. God function** — funzione che fa più cose insieme.

```python
# PRIMA
def handle_request(file_path, output_path, verbose):
    data = open(file_path).read()
    lines = [l for l in data.split("\n") if l.strip()]
    result = []
    for line in lines:
        processed = line.upper().strip()
        if verbose:
            print(f"Processing: {line}")
        result.append(processed)
    with open(output_path, "w") as f:
        f.write("\n".join(result))
    return len(result)
```

```python
# DOPO
def read_lines(file_path: Path) -> list[str]:
    return [
        line
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

def process_line(line: str) -> str:
    return line.upper().strip()

def write_output(lines: list[str], output_path: Path) -> None:
    output_path.write_text("\n".join(lines), encoding="utf-8")

def handle_request(file_path: Path, output_path: Path) -> int:
    lines = read_lines(file_path)
    processed = [process_line(line) for line in lines]
    write_output(processed, output_path)
    return len(processed)
```

Attenzione: il parametro `verbose` con `print()` è un side effect
nascosto. In questo esempio è stato rimosso (breaking change). Se deve
essere mantenuto, segnalalo in `## Note` e usa `logging`, non `print`.

**2. Boolean trap** — parametro booleano che cambia il comportamento
della funzione.

```python
# PRIMA
def get_data(source, use_cache):
    if use_cache:
        return _from_cache(source)
    return _from_network(source)
```

```python
# DOPO
def get_data_cached(source: str) -> Data:
    """Recupera dati dalla cache locale."""
    return _from_cache(source)

def get_data_fresh(source: str) -> Data:
    """Recupera dati freschi dalla rete."""
    return _from_network(source)
```

**3. Nested conditionals profondi** — più di 2-3 livelli di `if`
annidati.

```python
# PRIMA
def validate(data):
    if data is not None:
        if "name" in data:
            if len(data["name"]) > 0:
                if data["name"].isalpha():
                    return True
    return False
```

```python
# DOPO (guard clause)
def validate(data: dict | None) -> bool:
    if data is None:
        return False
    if "name" not in data:
        return False
    name = data["name"]
    return len(name) > 0 and name.isalpha()
```

**4. Duplicazione con variazione minima** — funzioni quasi identiche
che differiscono per un parametro.

```python
# PRIMA
def load_generator_skills():
    return Path("skills/python_generation/SKILL.md").read_text()

def load_review_skills():
    return Path("skills/code_review/SKILL.md").read_text()
```

```python
# DOPO
def load_skill(skill_name: str) -> str:
    path = Path(f"skills/{skill_name}/SKILL.md")
    if not path.exists():
        raise FileNotFoundError(f"Skill non trovata: {skill_name}")
    return path.read_text(encoding="utf-8")
```

**5. Dipendenza hardcoded non iniettabile** — classe che istanzia
internamente una dipendenza, rendendola non sostituibile nei test.

```python
# PRIMA
class GeneratorAgent:
    def __init__(self):
        self.client = AnthropicClient(api_key=os.getenv("KEY"))
```

```python
# DOPO
class GeneratorAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
```

**6. Magic number e magic string** — letterali numerici o stringhe
senza nome che rappresentano un concetto.

```python
# PRIMA
if quality_score < 0.85:
    retry()
if len(content) > 4000:
    truncate()
```

```python
# DOPO
QUALITY_THRESHOLD: float = 0.85
MAX_INPUT_TOKENS: int = 4000

if quality_score < QUALITY_THRESHOLD:
    retry()
if len(content) > MAX_INPUT_TOKENS:
    truncate()
```

**7. Eccezione troppo generica** — `except Exception` che cattura
tutto, senza handling specifico.

```python
# PRIMA
try:
    result = process(data)
except Exception:
    result = None
```

```python
# DOPO
try:
    result = process(data)
except ProcessingError as e:
    logger.warning("Processing fallito per input %.50s: %s", data, e)
    result = None
```

### 4.5 Tecnica: Extract Method

Quando una funzione è lunga (> 40 righe), identifica blocchi che:

- Hanno un commento sopra che spiega cosa fanno
- Potrebbero avere un nome proprio descrittivo
- Sono coesi internamente (operano sugli stessi dati)

Estraili come funzioni private con docstring minima.

```python
# PRIMA
def run(task):
    # validate input
    if not task.file_path.exists():
        raise FileNotFoundError(...)
    if task.language not in SUPPORTED:
        raise ValueError(...)

    # load skills
    skills = []
    for name in SKILL_MAP[task.command]:
        skills.append(load_skill(name))

    # generate
    prompt = build_prompt(task, skills)
    return llm.complete(prompt)
```

```python
# DOPO
def run(self, task: TaskInput) -> str:
    _validate_task(task)
    skills = _load_skills_for(task.command)
    return _generate(task, skills)

def _validate_task(task: TaskInput) -> None:
    if not task.file_path.exists():
        raise FileNotFoundError(f"File non trovato: {task.file_path}")
    if task.language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Linguaggio non supportato: {task.language}")

def _load_skills_for(command: str) -> list[Skill]:
    return [load_skill(name) for name in SKILL_MAP[command]]

def _generate(task: TaskInput, skills: list[Skill]) -> str:
    return self.llm.complete(build_prompt(task, skills))
```

## 5. Formato dell'output

L'output ha tre sezioni: due obbligatorie, una condizionale.

### Sezione obbligatoria: `## Modifiche apportate`

Lista delle modifiche applicate. Ogni voce ha tre parti:

- Pattern applicato (es. Extract Method, Guard Clause, Dependency
  Injection)
- Cosa è cambiato (riferimento concreto al codice)
- Perché (beneficio tecnico atteso, non estetico)

Esempio:

```
## Modifiche apportate

- Extract Method: separata validazione in `_validate_task()`
  → la funzione principale ora ha una sola responsabilità

- Guard clause: rimossi 3 livelli di nesting in `validate()`
  → leggibile linearmente senza tracciare lo stato dei branch

- Dependency injection: `LLMClient` ora iniettato nel costruttore
  → testabile con `MockLLMClient` senza chiamate reali
```

### Sezione obbligatoria: `## Codice refactorizzato`

Il codice completo, eseguibile, con tutte le modifiche applicate.
Niente diff. Niente commenti tipo "// invariato". Il file intero
nella sua forma finale.

```
## Codice refactorizzato

```python
[codice completo e funzionante]
```
```

### Sezione condizionale: `## Note`

Includila SOLO se hai almeno una di queste situazioni:

- Bug trovato nel codice originale (vedi protocollo sezione 4.2)
- Comportamento ambiguo che hai dovuto interpretare
- Breaking change intenzionale con giustificazione
- Suggerimenti per test post-refactoring

Se non hai nessuna di queste situazioni, **ometti completamente la
sezione**. Non scrivere "Nessuna nota" o equivalenti.

## 6. Esempi

**Output scorretto** — refactoring che cambia il comportamento:

```python
# Originale
def load_config(path):
    try:
        with open(path) as f:
            return yaml.load(f.read())
    except:
        return {}
```

```python
# Refactoring "migliorato" (scorretto)
def load_config(path: Path) -> dict[str, Any]:
    """Carica configurazione da file YAML."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```

**Perché è scorretto**: il refactoring cambia il comportamento su due
casi:

1. Il file non esiste → originale ritorna `{}`, nuovo lancia
   `FileNotFoundError`
2. Il YAML è malformato → originale ritorna `{}`, nuovo lancia
   `yaml.YAMLError`

I chiamanti potrebbero contare sul comportamento "ritorna sempre dict
vuoto su errore". Il refactoring rompe questo contratto.

**Output corretto** — stesso refactoring fatto bene:

```python
# Refactoring corretto
def load_config(path: Path) -> dict[str, Any]:
    """Carica configurazione da file YAML.

    Ritorna dict vuoto se il file non esiste o e' malformato.
    """
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}
```

**Perché funziona**: stesso comportamento osservabile (dict vuoto su
errore), ma:

- Type hints completi
- `yaml.safe_load` invece di `yaml.load` (vulnerability fix —
  segnalata in `## Note` come bug originale)
- `except` specifico invece di nudo (cattura `KeyboardInterrupt` e
  `SystemExit` è stato eliminato — questo è un cambio di comportamento,
  ma documentato come bug fix intenzionale nella `## Note`)

In questo caso il refactor **deve essere accompagnato** da una nota:

```
## Note

**BUG TROVATO (corretto durante il refactor, vedi sotto):**
1. yaml.load esegue costruttori Python arbitrari (vulnerability).
   Sostituito con yaml.safe_load.
2. except nudo catturava KeyboardInterrupt e SystemExit. Sostituito
   con eccezioni specifiche.

Entrambi sono bug fix di sicurezza intenzionali. Il comportamento su
input validi e' invariato. Verificare con test che i chiamanti non
dipendano dal vecchio comportamento di soppressione errori globale.
```

## 7. Vincoli operativi assoluti

- **Comportamento osservabile invariato**: per ogni input ammesso dalla
  funzione originale, la nuova versione deve produrre lo stesso output
  e sollevare le stesse eccezioni. Edge case inclusi.
- **Bug non corretti silenziosamente**: ogni bug trovato è dichiarato
  in `## Note`. Nessun bug fix nascosto dentro il refactoring.
- **Side effect preservati**: `print`, `logger`, scrittura file,
  modifiche a variabili globali — tutto preservato come nell'originale,
  o esplicitamente documentato come breaking change in `## Note`.
- **Nessuna nuova dipendenza esterna**: il refactoring non aggiunge
  import di pacchetti pip non già presenti nel file originale.
  Eccezione: type hints da `typing` o `pathlib` (stdlib).
- **Nessun magic number introdotto**: se aggiungi una costante durante
  il refactor, è nominata (UPPER_SNAKE) e tipizzata.
- **Type hints sulle funzioni nuove**: ogni funzione privata estratta
  ha type hints completi e docstring minima (una riga).

## 8. Self-check criteria

Quando valuti la tua bozza di refactoring, applica questi criteri con
default conservativo. In caso di dubbio su un criterio: non passa.

- **Invariante comportamentale**: per ogni funzione modificata, il
  comportamento su input valido, input None/vuoto, e edge case è
  identico all'originale?
- **Stesse eccezioni**: le stesse eccezioni vengono lanciate sui
  stessi input errati?
- **Side effect identici**: `print`, log, scrittura file, mutazioni
  globali sono preservate (o documentate in `## Note`)?
- **Bug non nascosti**: nessun bug corretto silenziosamente? Se sì,
  documentato in `## Note`?
- **Nomi descrittivi**: ogni funzione estratta ha un nome che descrive
  l'intenzione, non l'implementazione (`_validate_task` ✓, `_helper1`
  ✗)?
- **Type hints completi**: tutte le funzioni nuove e modificate hanno
  type hints su parametri e return type?
- **Nessun magic number**: i letterali numerici sono costanti nominate
  quando rappresentano un concetto?

### Severity assignment

- `critical`: il refactoring cambia il comportamento osservabile in
  modo non documentato; un bug è stato corretto silenziosamente;
  un'eccezione che veniva lanciata ora non lo è (o viceversa).
- `high`: una funzione estratta non ha type hints; un side effect è
  stato rimosso senza nota; il codice refattorizzato non compila o
  ha syntax error.
- `medium`: il pattern anti-pattern identificato non è il più
  prioritario disponibile (es. risolvi magic number ignorando una god
  function nello stesso file); nomi di funzioni estratte poco
  descrittivi.
- `low`: lo stile dei nomi delle costanti potrebbe essere più
  uniforme; ordine delle funzioni nel file subottimale.

## 9. Rubrica deterministica del quality_score

Il quality_score finale è la media pesata di quattro criteri,
ciascuno valutato da 0.0 a 1.0:

- **Invariante comportamentale** (peso 0.40): il refactoring preserva
  il comportamento osservabile su ogni input ammesso dall'originale.
  Questo è il criterio dominante: un refactoring che cambia
  comportamento non è un refactoring, indipendentemente da quanto sia
  "bello" il risultato.
- **Conformità Python** (peso 0.25): type hints completi, naming
  conforme, no magic number, no `except` generico, no dipendenza
  hardcoded nelle funzioni nuove.
- **Strutturazione formale** (peso 0.20): le tre sezioni dell'output
  sono presenti con titoli esatti; la sezione `## Note` è inclusa
  solo se ha contenuto reale.
- **Qualità delle modifiche** (peso 0.15): i pattern applicati sono i
  più prioritari disponibili; i nomi delle funzioni estratte sono
  descrittivi dell'intenzione.

Soglia di validità: `quality_score < 0.70` → `is_valid: false`,
blocca l'output e avvia la rigenerazione.

Nota: il peso 0.40 sull'invariante comportamentale riflette il fatto
che è la regola più importante della skill. Un refactoring tecnicamente
bello che cambia comportamento è peggio di un refactoring imperfetto
che lo preserva.
