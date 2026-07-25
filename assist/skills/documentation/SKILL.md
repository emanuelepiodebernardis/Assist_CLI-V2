---
# === Campi v2.5 (invariati) ===
name: documentation
version: 3.0
applies_to: [explain]
priority: 80
inject_position: middle
max_output_words: 150
load_examples: false
load_templates: false
conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  project_rules ha sempre precedenza sulle regole di questa skill.
  Regola specifica di questa skill: il limite di parole della modalita'
  attiva (150 concise, 500 verbose) ha precedenza su ogni regola
  stilistica. Se il contenuto utile richiederebbe piu' parole, taglia
  per priorita': mantieni COSA FA, ometti il resto.
self_check_persona: adversarial
_persona_text: >
  Sei il lettore che apre la documentazione per la prima volta. Il tuo
  default e' RIFIUTARE le spiegazioni che ripetono il codice o spiegano
  l'ovvio. La domanda che ti fai e': dopo aver letto questa spiegazione,
  so qualcosa che non sapevo leggendo solo il codice? Se la risposta e'
  no, la spiegazione e' rumore.
description: >
  Regole per la spiegazione e documentazione di codice Python. Include
  criteri di utilita' (cosa merita spiegazione), struttura per livello
  di complessita', standard docstring Google style, esempi di output
  calibrati per modalita' concise e verbose, regole anti-ridondanza
  applicate sistematicamente.

# === Campi v3.0 (Runtime Configuration) ===

task_type: prose

inputs:
  required:
    - raw_input                # contenuto del file Python da spiegare
    - semantic_context         # funzioni, classi (signature, complessità, docstring esistenti)
  optional:
    - cross_file_context       # function_calls (segnale "pubblico de facto")
    - options                  # dict CLI: depth (concise|full), verbose, ecc.

outputs:
  format: markdown
  # Nessun `sections` dichiarato: l'output assume tre forme alternative
  # (prosa libera, docstring Google style, commento inline). Non esistono
  # H2 obbligatori da verificare meccanicamente — la conformità formale
  # è giudicata dalla rubrica (sezione 9 del body).

process:
  max_corrections: 1
  quality_threshold: 0.70

verifier:
  syntax: noop                 # output prose/docstring/commento, niente AST
  format: noop                 # nessun set fisso di section headers
  coherence: rubric            # delega alla rubrica della sezione 9 del body
---

# documentation v3.0

## 1. Scopo della skill

Produrre spiegazioni e documentazione di codice Python esistente, in
prosa diretta o come docstring Google style. L'output deve aggiungere
informazione rispetto al codice, non riformularlo. Si distingue dal
task `review` (che identifica problemi) e dal task `generate` (che
produce codice nuovo).

## 2. Postura (come pensare al task)

Stai scrivendo per un lettore che ha già il codice davanti agli occhi.
Non devi descrivergli quello che vede. Devi dirgli quello che il codice
non dice da solo: il "perché", il contesto delle decisioni, gli edge
case non ovvi, le assunzioni nascoste.

Il tuo default è: la spiegazione aggiunge informazione. Se rimuovi una
frase e il codice dice ancora la stessa cosa, quella frase era rumore.

Anticipa tre tipi di violazioni ricorrenti del modello:

- **Parafrasare il codice in prosa**: "Il loop itera sulla lista delle
  skills". Il lettore vede già il loop. Inutile.
- **Spiegare la sintassi Python**: "L'if controlla la condizione e
  esegue il blocco se vera". Il lettore conosce Python, o non è il
  tuo problema.
- **Riformulare i commenti esistenti**: se il codice ha già un
  commento `# offset di 1 per l'API`, non scrivere "come si vede dal
  commento, c'è un offset di 1".

Test pratico: se rimuovi la spiegazione e il codice dice la stessa
cosa, la spiegazione era inutile.

## 3. Dati del context utilizzati

### Reference (Layer 3, stabile tra run)
- `project_rules` (sempre presente)
- `documentation` (questa skill)

### Working artifacts (Layer 4, specifico al run)
- `task.file_path` — file Python da documentare/spiegare
- `task.raw_input` — contenuto del file
- `task.options.depth` — `concise` (default) o `full` (flag
  `--depth full`)
- `semantic_context.functions` — funzioni del file con signature,
  complessità, docstring esistente
- `semantic_context.classes` — classi del file
- `cross_file_context.function_calls` — chi chiama le funzioni del
  file altrove (segnale: queste funzioni sono parte dell'interfaccia
  pubblica del modulo)

### Opzionali (versioni future)
- `task.options.depth` — se assente, applica la regola degradata:
  usa modalità `concise`.
- `git_history_context` — non ancora prodotto. Quando disponibile,
  conterrà la storia delle modifiche al file (utile per identificare
  decisioni di design implicite nei commit). Se assente: spiega solo
  il codice attuale, non inferire l'evoluzione storica.

## 4. Regole operative

### 4.1 Principio: cosa merita una spiegazione

Documentazione utile risponde a domande che il codice non risponde da
solo. Documentazione inutile ripete il codice.

**UTILE — spiega il perché:**

```python
i = i + 1  # offset: l'API restituisce indici 0-based, noi 1-based
```

**INUTILE — ripete il cosa:**

```python
i = i + 1  # incrementa i
```

**UTILE — spiega un edge case non ovvio:**

```python
# Se skills è vuota, il modello riceve solo project_rules.
# Questo è intenzionale: project_rules è sempre presente.
```

**INUTILE — spiega comportamento ovvio:**

```python
# Itera sulla lista delle skills
for skill in skills:
```

### 4.2 Struttura della spiegazione

Quando spieghi una funzione o classe, segui questo ordine. Ometti le
sezioni senza contenuto utile.

1. **COSA FA** (obbligatorio, 1-2 frasi)
   Responsabilità principale. Non i dettagli.

2. **COME FUNZIONA** (solo se non ovvio)
   Il meccanismo centrale. Non passo per passo se banale.

3. **EDGE CASE E ASSUNZIONI** (solo se rilevanti)
   Cosa presuppone. Cosa non gestisce.

4. **DIPENDENZE** (solo se non ovvie)
   Cosa deve esistere perché funzioni.

### 4.3 Calibrazione per modalità

**Modalità `concise`** (default, max 150 parole):

Copri solo COSA FA e il meccanismo principale se non ovvio. Ometti
tutto il resto.

Esempio di output `concise` corretto:

```
SkillResolver carica i file SKILL.md dal filesystem dato una lista di
nomi skill. Per ogni nome, legge prima il frontmatter YAML per decidere
se caricare anche examples/ e templates/, minimizzando il contesto
portato nel prompt del modello.

Presuppone che le skill esistano in skills/<nome>/SKILL.md. Lancia
SkillNotFoundError se una skill richiesta non esiste.
```

Questo esempio ha 54 parole. È il livello giusto per `concise`.

**Modalità `full`** (flag `--depth full`, max 500 parole):

Copri tutti e 4 i punti della struttura. Aggiungi pattern di design
usati, alternative considerate, esempi d'uso in contesto reale.

Esempio di output `full` corretto:

```markdown
### SkillResolver

**Responsabilità:** carica e restituisce skills dal filesystem,
ottimizzando il contesto portato al modello LLM.

**Come funziona:** per ogni nome skill ricevuto, costruisce il path
`skills/<nome>/SKILL.md`, legge il frontmatter YAML (senza caricare il
corpo), e decide se aggiungere examples/ e templates/ in base ai flag
`load_examples` e `load_templates`. Restituisce List[Skill] con il
contenuto pronto per l'iniezione nel prompt.

**Pattern usato:** Lazy loading — il corpo della skill viene letto solo
se necessario. Questo riduce l'uso della context window del modello del
40-60% su task semplici che non richiedono esempi.

**Assunzioni:** le skill esistono nella directory configurata. Non
gestisce skill remote o compresse.

**Dipendenze:** PyYAML per il frontmatter, pathlib per i path.
```

### 4.4 Cosa non spiegare mai

**NON spiegare la sintassi Python base:**

- ✗ "Il for loop itera sulla lista"
- ✗ "L'if controlla la condizione"
- ✗ "Il return restituisce il valore"

**NON spiegare comportamento ovvio dalla signature:**

- ✗ `def add(a: int, b: int) -> int:` non ha bisogno di spiegazione
- ✗ `def is_empty(lst: list) -> bool:` non ha bisogno di spiegazione

**NON riformulare commenti esistenti:**

Se il codice ha già `# offset di 1 per l'API`, non scrivere "Come si
vede dal commento, c'è un offset di 1 per l'API".

**NON spiegare cose che il nome descrive già:**

- ✗ "MAX_RETRIES è la costante che definisce il numero massimo di
  retry"

### 4.5 Docstring standard (Google style)

**Funzione semplice.**

```python
def load_skill(skill_path: Path) -> dict[str, Any]:
    """Carica i metadati di una skill dal filesystem.

    Args:
        skill_path: Percorso al file SKILL.md.

    Returns:
        Dict con frontmatter YAML. Contiene sempre 'name',
        'version', 'applies_to'.

    Raises:
        FileNotFoundError: Se skill_path non esiste.
        ValueError: Se il frontmatter è assente o malformato.
    """
```

**Funzione con `Example`.**

Aggiungi `Example` quando la signature non è autoesplicativa o quando
l'output ha una struttura non ovvia.

```python
def build_prompt(task: TaskInput, skills: list[Skill]) -> tuple[str, str]:
    """Costruisce system prompt e user prompt per il modello.

    Args:
        task: Input strutturato con comando, file e opzioni.
        skills: Liste di Skill caricate dal SkillResolver.

    Returns:
        Tupla (system_prompt, user_prompt). Il codice sorgente
        è nel user_prompt dentro tag <code>.

    Example:
        >>> task = TaskInput(command="review", file_path=Path("m.py"))
        >>> skills = resolver.load(["project_rules", "code_review"])
        >>> system, user = build_prompt(task, skills)
        >>> "<code>" in user
        True
    """
```

**Classe.**

```python
class SkillResolver:
    """Carica skills dal filesystem su richiesta degli agenti.

    Legge il frontmatter di ogni SKILL.md prima del corpo,
    minimizzando il contesto portato al modello.

    Attributes:
        skills_root: Directory radice delle skills.

    Example:
        >>> resolver = SkillResolver(Path("assist/skills"))
        >>> skills = resolver.load(["project_rules", "code_review"])
        >>> len(skills)
        2
    """
```

**Quando omettere o ridurre la docstring.**

Una sola riga (o nessuna) per:

- Metodi privati (`_nome`) con logica ovvia
- Property getter semplici
- `__init__` quando la docstring della classe descrive gli attributi
- Funzioni di test: il nome è la documentazione

### 4.6 Commenti inline: quando sì e quando no

**SÌ — spiega decisioni non ovvie:**

```python
MAX_RETRIES = 2  # >2 aumenta la latenza senza beneficio misurabile
```

**SÌ — spiega workaround o bug conosciuti:**

```python
result = value + 1  # API usa indici 0-based, noi 1-based
```

**SÌ — spiega regex o espressioni complesse:**

```python
PLACEHOLDER_RE = re.compile(r"<[A-Z_]+>|TODO:|FIXME:")
# trova placeholder non intenzionali nell'output LLM
```

**SÌ — separa sezioni logiche in funzioni lunghe:**

```python
# ── Validazione input ─────────────────────────────────
```

**NO — ripete il codice:**

```python
items = []  # lista vuota
```

**NO — storia del codice (appartiene al commit message):**

```python
# 2024-03-15: modificato per gestire il caso edge
```

**NO — spiega il "cosa" invece del "perché":**

```python
for item in items:   # itera sugli item
```

## 5. Formato dell'output

L'output dipende dal sotto-task. Tre forme possibili.

### Forma 1: Spiegazione di un file o modulo (task `explain`)

Prosa diretta. Nessun header se il contenuto è breve. Se più
componenti distinte (più classi, più funzioni complesse): usa `###`
per separarle.

**Vietato:**

- Prefazione ("Ecco la spiegazione del codice:")
- Postfazione ("Spero che questa spiegazione sia chiara!")
- Header inutili quando il contenuto è una singola spiegazione lineare

### Forma 2: Docstring per funzione o classe

Solo il blocco docstring, formato Google style. Pronto per essere
incollato dentro la funzione/classe esistente.

```python
"""Breve descrizione in una riga.

Args:
    param1: Descrizione.

Returns:
    Descrizione.

Raises:
    ValueError: Quando.
"""
```

### Forma 3: Commento inline

Una sola riga, dopo `#`, max 80 caratteri totali (incluso il codice
della riga). Spiega il "perché", mai il "cosa".

```python
MAX_RETRIES = 2  # >2 aumenta latenza senza beneficio misurabile
```

### Limite di parole

Modalità `concise` (default, attivo se `task.options.depth` non è
`full`): massimo 150 parole totali per il contenuto della spiegazione.
Conta prima di restituire. Se superi, taglia per priorità: mantieni
COSA FA, ometti EDGE CASE e DIPENDENZE.

Modalità `full` (flag `--depth full`): massimo 500 parole. Copri tutti
e 4 i punti della struttura.

## 6. Esempi

**Output scorretto** — spiegazione che ripete il codice:

> La funzione `load_skill` accetta un parametro `skill_path` di tipo
> `Path` e restituisce un dizionario. Prima controlla se il file
> esiste, e se non esiste lancia FileNotFoundError. Poi legge il
> contenuto del file con read_text e lo passa a `_parse_frontmatter`.
> Infine restituisce il dizionario ritornato da `_parse_frontmatter`.

**Perché è scorretto**: parafrasa il codice riga per riga. Il lettore
ha già la signature e il corpo della funzione davanti. Questa
spiegazione non aggiunge informazione, occupa solo spazio.

**Output corretto** — stessa funzione, spiegazione utile:

> `load_skill` è il punto di ingresso del SkillResolver. Carica solo
> il frontmatter YAML, mai il corpo: minimizza i token spediti al
> modello, scaricando il corpo solo quando `load_examples` o
> `load_templates` sono attivi.
>
> Lancia `ValueError` (non `FileNotFoundError`) se il file esiste ma
> il frontmatter è malformato. Questa distinzione è importante per il
> caller: file mancante è un problema di configurazione, frontmatter
> rotto è un problema della skill stessa.

**Perché funziona**: nomina il design pattern (lazy loading), spiega
una decisione non ovvia (la distinzione tra `ValueError` e
`FileNotFoundError`), dà al lettore informazione utile per usare la
funzione correttamente.

## 7. Vincoli operativi assoluti

- **Nessuna parafrasi del codice**: se rimuovendo la frase il codice
  dice la stessa cosa, la frase è rumore e va eliminata.
- **Nessuna spiegazione della sintassi Python base**: il lettore
  conosce Python, o la skill non è applicabile.
- **Nessun commento del "cosa" inline**: i commenti inline spiegano
  solo il "perché". Il "cosa" è già nel codice.
- **Args/Returns/Raises corrispondono al codice**: se il docstring
  dichiara `Raises: ValueError`, la funzione deve effettivamente
  lanciare `ValueError`. Mai documentare eccezioni che non vengono
  sollevate.
- **Tipi nei docstring coerenti con i type hints**: non ripetere i
  tipi nei `Args:` (sono già nella signature), ma quando descrivi il
  valore di ritorno o le eccezioni, usa nomi coerenti con quelli
  della signature.
- **Example eseguibile**: se il docstring contiene `Example`, deve
  essere sintatticamente valido Python ed eseguibile in un interprete
  con gli import corretti. Mai pseudo-example.
- **Limite di parole rispettato**: conta sempre prima di restituire.

## 8. Self-check criteria

Quando valuti la tua bozza di documentazione, applica questi criteri
con default conservativo. In caso di dubbio su un criterio: non passa.

- **Utilità**: ogni frase risponde a una domanda che il codice non
  risponde da solo? Test: rimuovi la frase, il significato cambia?
- **No parafrasi**: nessuna frase riformula il codice in prosa? Nessun
  commento ripete il nome del costrutto (`# loop`, `# if check`)?
- **No sintassi base**: nessuna spiegazione di for, if, return, type
  base?
- **Args/Returns corretti**: i parametri documentati corrispondono
  alla signature? I tipi sono coerenti? Le descrizioni non ripetono
  i nomi?
- **Raises corretto**: ogni eccezione dichiarata viene effettivamente
  lanciata dalla funzione? Nessuna eccezione lanciata è omessa nel
  Raises?
- **Example valido**: se presente, è sintatticamente corretto ed
  eseguibile?
- **Limite di parole**: il totale è entro la modalità attiva
  (150 concise, 500 verbose)?
- **Struttura ordinata**: COSA FA prima di COME FUNZIONA prima di
  EDGE CASE prima di DIPENDENZE?

### Severity assignment

- `critical`: docstring dichiara `Raises: ExceptionX` ma la funzione
  non la lancia (o viceversa, omette eccezione effettivamente
  lanciata); `Example` non eseguibile; spiegazione che afferma cose
  false sul comportamento del codice.
- `high`: parafrasi sistematica del codice (più di metà delle frasi
  sono ripetizioni); spiegazione della sintassi Python base; tipi
  nei docstring incoerenti con i type hints.
- `medium`: ridondanza occasionale (qualche frase ripete il codice);
  ordine della struttura non rispettato; modalità verbose usata
  quando concise sarebbe sufficiente.
- `low`: piccole imperfezioni stilistiche; lunghezza vicina al limite
  ma non superata.

## 9. Rubrica deterministica del quality_score

Il quality_score finale è la media pesata di quattro criteri,
ciascuno valutato da 0.0 a 1.0:

- **Utilità informativa** (peso 0.35): ogni frase aggiunge
  informazione rispetto al codice; nessuna parafrasi sistematica;
  nessuna spiegazione di sintassi base. Questo è il criterio
  dominante: una documentazione che parafrasa il codice non passa,
  indipendentemente da quanto sia ben strutturata.
- **Correttezza tecnica** (peso 0.30): Args/Returns/Raises
  corrispondono al codice; tipi coerenti con i type hints; `Example`
  (se presente) è eseguibile; nessuna affermazione falsa sul
  comportamento del codice.
- **Struttura e calibrazione** (peso 0.20): ordine COSA→COME→EDGE→
  DIPENDENZE rispettato; modalità (concise/verbose) coerente con
  `task.options.depth`; limite di parole rispettato.
- **Conformità formale** (peso 0.15): docstring Google style ben
  formata; nessuna prefazione/postfazione; commenti inline solo per
  il "perché".

Soglia di validità: `quality_score < 0.70` → `is_valid: false`,
blocca l'output e avvia la rigenerazione.

Nota: il peso 0.35 sull'utilità informativa riflette il fatto che è
la regola più importante della skill. Una documentazione corretta dal
punto di vista tecnico ma che parafrasa il codice è peggio di una
documentazione un po' imperfetta ma genuinamente utile. La
documentazione inutile è dannosa: occupa spazio cognitivo del lettore
senza dargli niente in cambio.
