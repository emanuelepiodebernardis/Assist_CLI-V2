# SKILL Format — Hybrid Canonical

> Specifica del formato delle skill di Assist CLI.
>
> Il documento è organizzato in due parti:
>
> - **Parte I (sezioni 1-10)**: standard v2.5 Hybrid Canonical, in vigore
>   da Assist CLI v0.2.0. Tutte le skill correnti seguono questo standard.
>
> - **Parte II (sezioni 11-17)**: estensione v3.0 — Runtime Configuration,
>   introdotta in Assist CLI v0.3.0. È un'estensione **opzionale** del
>   frontmatter che permette al `SkillResolver` di parsare campi tipizzati
>   e al sistema di usarli a runtime. Le skill v2.5 continuano a funzionare
>   invariate.

---

## Indice

### Parte I — Standard v2.5

1. Filosofia e principi
2. Posizione e nome del file
3. Frontmatter YAML
4. Struttura del corpo
5. Stile narrativo: regole prescrittive
6. Esempi nel corpo
7. Self-check e rubrica deterministica
8. Anti-pattern (cosa non fare)
9. Checklist di conformità
10. Esempio canonical minimo

### Parte II — Estensione v3.0

11. Motivazione e ambito v3.0
12. Frontmatter v3.0 (campi aggiuntivi)
13. Modello Pydantic Skill esteso
14. Retrocompatibilità e convivenza v2.5 / v3.0
15. Esempio: code_review migrata a v3.0
16. Migrazione: cosa cambia, cosa resta uguale
17. Checklist v3.0

---

## 1. Filosofia e principi

Una skill di Assist CLI è **codice configurazionale leggibile**. Tre proprietà
non negoziabili:

**Source, non output.** La skill è il sorgente che produce il comportamento
dell'agent. Se l'output dell'agent è sbagliato in modo ricorrente, si modifica
la skill, non l'output. Le skill devono essere editabili da chiunque sappia
leggere markdown, non solo da un developer.

**Layered context aware.** Ogni skill dichiara esplicitamente quali campi del
context strutturale legge, distinguendo tra reference material (Layer 3:
stabile tra run, regole e convenzioni) e working artifacts (Layer 4: specifico
al run, codice in input, diff, output di stage precedenti). Questa distinzione
ricalca l'Interpretable Context Methodology di Van Clief e McDermott
(arXiv:2603.16021) e ha implicazioni concrete: il modello processa
diversamente regole stabili e dati transitori.

**Doppio target: umano e parser.** Il frontmatter ha campi dichiarativi
(slug brevi: `adversarial`, `project_rules_wins`) leggibili da codice futuro
(sistema configurazionale v0.3.0+) e campi espansi (testo descrittivo)
leggibili da umani e da LLM oggi. Entrambi vincono.

Le skill non sono documenti tecnici neutri. Sono **prompt prescrittivi**.
Modellano la postura dell'agent, non solo le sue regole.

---

## 2. Posizione e nome del file

Ogni skill vive in:

```
assist/skills/<skill_name>/SKILL.md
```

Dove `<skill_name>` è uno snake_case identico al valore del campo `name`
nel frontmatter. Esempi:

- `assist/skills/project_rules/SKILL.md`
- `assist/skills/pytest_generation/SKILL.md`
- `assist/skills/diff_review/SKILL.md`

Il `SkillResolver` (in `assist/core/skill_resolver.py`) carica le skill da
questa posizione. Nomi diversi o file fuori da questa struttura non vengono
trovati.

Una skill può avere file aggiuntivi nella propria cartella:

```
assist/skills/<skill_name>/
├── SKILL.md              (obbligatorio)
├── examples/             (opzionale, caricato se load_examples: true)
│   ├── good_example.py
│   └── bad_example.py
└── templates/            (opzionale, caricato se load_templates: true)
    └── starter.py
```

Per ora, `examples/` e `templates/` non sono caricati automaticamente dal
sistema. I flag `load_examples` e `load_templates` nel frontmatter sono
predisposti per la v0.3.0+.

---

## 3. Frontmatter YAML

Il frontmatter sta tra due righe `---` ed è in YAML standard. Contiene
**campi dichiarativi** (slug brevi, parsabili) e **campi espansi**
(testo descrittivo, prefissati con underscore).

### 3.1 Campi obbligatori

```yaml
---
name: <skill_name>
version: 2.5
applies_to: [<task>, <task>, ...]
priority: <number>
inject_position: <first | middle | last>
max_output_words: <number | "unlimited">
conflict_resolution: <slug>
self_check_persona: <slug>
---
```

**`name`** (string, snake_case): identificatore univoco. Deve corrispondere
al nome della cartella che contiene la skill.

**`version`** (string): `2.5` per lo standard ibrido. Le skill ancora in
formato v2.0 hanno `version: 2.0` e vanno migrate. Le skill che adottano
l'estensione runtime usano `version: 3.0` (vedi Parte II).

**`applies_to`** (list of strings): task per cui la skill è applicabile.
Valori validi: `generate`, `review`, `refactor`, `explain`, `test`, `diff`,
`repo` (futuro). Una skill può applicarsi a più task. `project_rules` ha
`applies_to: [generate, review, refactor, explain, test, diff]`.

**`priority`** (integer): numero da 0 a 100. Controlla l'ordine di iniezione
nel prompt finale quando più skill sono caricate per uno stesso task.
Valori più alti vengono iniettati per **ultimi** (= hanno più peso nel prompt).
Convenzione:

- `100` — riservato per `project_rules` (sempre l'ultimo)
- `80` — skill specifiche al task
- `60` — skill di supporto generiche
- `0-50` — skill complementari opzionali

**`inject_position`** (enum): posizione di iniezione nel prompt:

- `first` — la skill viene iniettata in cima, prima delle altre
- `middle` — posizione standard tra altre skill
- `last` — la skill viene iniettata per ultima, ha precedenza
  semantica (è quella che il modello legge per ultima)

`project_rules` usa `inject_position: last` perché vuole essere "la voce
finale" del prompt.

**`max_output_words`** (integer o `"unlimited"`): vincolo di lunghezza
sull'output dell'agent. Coerente con la modalità default (concise).
Per modalità verbose (futuro), aggiungere `max_output_words_verbose`.

**`conflict_resolution`** (slug): cosa fare se questa skill confligge con
un'altra nel prompt. Valori validi:

- `project_rules_wins` — in caso di conflitto, `project_rules` ha precedenza
- `task_skill_wins` — la skill specifica al task ha precedenza
- `none` — nessun conflict resolution dichiarato (sconsigliato)

**`self_check_persona`** (slug): tipo di persona da assumere nel self-check.
Valori validi:

- `adversarial` — reviewer ostile, default è BLOCCARE
- `pedagogical` — reviewer didattico, suggerisce miglioramenti
- `permissive` — reviewer benevolo, blocca solo errori gravi

La maggior parte delle skill usa `adversarial`. Le skill per task di
spiegazione potrebbero usare `pedagogical`.

### 3.2 Campi opzionali

```yaml
load_examples: <bool>
load_templates: <bool>
description: <string multilinea>
```

**`load_examples`** / **`load_templates`** (bool, default false): se `true`,
il `SkillResolver` carica anche i file in `examples/` e `templates/` della
skill. Oggi non implementato. Predisposto per v0.3.0+.

**`description`** (multilinea YAML `>`): descrizione human-readable della
skill, ~3-5 righe. Va in cima al frontmatter dopo `name` e `version`.

### 3.3 Campi espansi (prefissati con underscore)

I campi dichiarativi sono **slug** parsabili. Per ognuno di essi che ha un
significato pragmatico (cioè un comportamento concreto associato), serve
una **versione espansa** descrittiva, prefissata con underscore:

```yaml
self_check_persona: adversarial
_persona_text: >
  Sei un senior engineer che deve decidere se bloccare un merge in produzione.
  Il tuo default e' BLOCCARE. Cerca attivamente motivi per non approvare.
  Una review che trova zero problemi su codice non triviale e' quasi sempre
  una review non fatta bene.

conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  In caso di conflitto con project_rules, project_rules ha sempre precedenza.
  Le regole specifiche di questa skill cedono il passo a project_rules su
  qualsiasi punto in cui i due si sovrappongono.
```

**Convenzione**: ogni slug dichiarativo che descrive un comportamento (non
una semplice configurazione tecnica) **deve** avere un campo `_<nome>_text`
con la sua versione espansa. Lo slug serve al codice futuro (v0.3.0).
Il testo serve all'LLM oggi (viene iniettato nel prompt) e all'umano che
legge la skill.

Slug che NON richiedono versione espansa: `name`, `version`, `priority`,
`inject_position`, `applies_to`, `max_output_words`, `load_examples`,
`load_templates`.

Slug che **richiedono** versione espansa: `self_check_persona`,
`conflict_resolution`, ed eventuali nuovi slug pragmatici aggiunti in futuro.

---

## 4. Struttura del corpo

Dopo il frontmatter, il corpo della skill segue **nove sezioni canoniche**,
in questo ordine esatto. Sezioni opzionali (marcate `[opzionale]`) possono
essere omesse se non hanno contenuto rilevante; le altre sono obbligatorie.

```markdown
# <skill_name> v2.5

## 1. Scopo della skill
## 2. Postura (come pensare al task)
## 3. Dati del context utilizzati
## 4. Regole operative
## 5. Formato dell'output
## 6. Esempi  [opzionale ma fortemente consigliato]
## 7. Vincoli operativi assoluti
## 8. Self-check criteria
## 9. Rubrica deterministica del quality_score
```

### Sezione 1 — Scopo della skill (obbligatoria, ~80 parole)

Cosa fa la skill in 2-4 frasi. Quale task supporta, quale output produce,
qual è la differenza rispetto ad altre skill simili.

Esempio dal `pytest_generation`:

> Generare test pytest per un file Python target. I test devono riflettere il
> comportamento osservabile del file, non inventarne uno nuovo. La copertura
> privilegia profondità su ampiezza: meglio dieci test ben pensati che venti
> ripetitivi.

Cosa **non** includere: scelte implementative (ne parla la sezione 4),
formato output (ne parla la 5), criteri di validazione (ne parlano la 8-9).

### Sezione 2 — Postura (obbligatoria, ~100-200 parole)

Come il modello deve **pensare** mentre svolge il task. È la sezione narrativa
e prescrittiva. Modella la postura mentale, anticipa i fallimenti tipici del
modello (es. eccesso di gentilezza, vaghezza, omissione di edge case) e li
neutralizza.

Esempio dal `code_review` (riformulato per v2.5):

> Non stai valutando il codice di qualcuno che conosci. Stai facendo una
> review per decidere se questo codice puo' andare in produzione su un sistema
> usato da utenti reali.
>
> Il tuo default e': questo codice ha problemi. Il tuo lavoro e' trovarli
> prima che lo facciano gli utenti.
>
> Una review che trova zero problemi su codice non triviale e' quasi sempre
> una review non fatta bene.

Questa sezione è quello che le skill v2.0 storiche fanno meglio. Mantienila
forte. Frasi nette, no qualificatori vaghi tipo "potrebbe essere utile".

### Sezione 3 — Dati del context utilizzati (obbligatoria)

Dichiarazione esplicita dei campi del context strutturale letti dalla skill.
Distingui chiaramente Layer 3 (reference, stabile) da Layer 4 (working,
specifico al run).

Struttura:

```markdown
## 3. Dati del context utilizzati

### Reference (Layer 3, stabile tra run)
- `project_rules` (sempre presente nel prompt)
- altre skill applicabili al task (vedi `registry.yaml`)

### Working artifacts (Layer 4, specifico al run)
- `task.raw_input` — <descrizione di cosa contiene per questa skill>
- `semantic_context.functions` — lista funzioni del file target
- `semantic_context.classes` — lista classi del file target
- `code_quality_context.complexity_warnings` — funzioni complesse
- `cross_file_context.function_calls` — chi chiama cosa nel progetto

### Opzionali (versioni future)
- `<campo_futuro>` — non ancora prodotto dal sistema. Quando disponibile,
  applicare la regola degradata descritta nella sezione 4.X.
```

Per ogni campo, una riga descrittiva: cosa contiene, come viene usato dalla
skill. Non duplicare la documentazione del campo (vive in
`assist/schemas/models.py`), ma spiegare **a cosa serve questa skill**.

Se la skill prevede di leggere campi non ancora prodotti dal sistema, listali
in "Opzionali" e descrivi la regola degradata (cosa fare quando il campo è
assente).

### Sezione 4 — Regole operative (obbligatoria)

Il cuore prescrittivo della skill. Le regole concrete che governano il
comportamento dell'agent. Stile narrativo con esempi inline ammessi.

Sotto-sezioni tipiche (adattare al dominio della skill):

- Scala di severità con definizioni precise
- Ordine di analisi (se applicabile)
- Pattern preferiti / pattern proibiti
- Convenzioni di naming, struttura, organizzazione
- Tecniche specifiche del dominio (Extract Method, Guard Clause, ecc.)

Esempio strutturale (dal `code_review`):

```markdown
### 4.1 Scala di severità

**CRITICO** — blocca il merge
Il codice non funziona, ha un bug confermato, ...
Esempi concreti:
- KeyError, IndexError su percorso principale
- except: pass che nasconde errori reali
- ...

**ALTO** — fortemente consigliato
Il codice funziona ma fallisce su edge case prevedibili, ...

### 4.2 Ordine di analisi

Analizza in questo ordine. Ogni livello e' piu' importante del successivo.

1. CORRETTEZZA
   - Il codice fa quello che sembra voler fare?
   - I casi limite sono gestiti?
2. SICUREZZA
   ...
```

Lunghezza tipica della sezione 4: 300-800 parole, dipende dalla complessità
del task. Per skill complesse (`refactor`, `code_review`) sono normali
1000+ parole. Per skill semplici (`documentation`) possono bastare 300.

### Sezione 5 — Formato dell'output (obbligatoria)

Struttura esatta dell'output dell'agent. Cosa contiene, quali sezioni
markdown, vincoli formali (no markdown fence, no prefazioni, ecc.).

Se l'output è codice puro (es. `pytest_generation`, `python_generation`),
specifica i vincoli stretti:

```markdown
- Nessun blocco markdown (no triple backtick di apertura/chiusura)
- Nessuna prefazione
- Nessuna postfazione
- Solo: shebang opzionale, docstring del modulo, import, classi/funzioni
```

Se l'output è prosa markdown (es. `code_review`, `diff_review`), specifica
la struttura delle sezioni obbligatorie e condizionali:

```markdown
### Sezioni obbligatorie
- `## Sommario` (sempre, max N parole)
- `## Modifiche rilevanti` (sempre, max N parole)

### Sezioni condizionali (incluse SOLO se hanno contenuto reale)
- `## Rischi` (max N parole)
- `## Suggerimenti` (max N parole)

### Vietato
- Sezioni condizionali presenti ma vuote con frasi tipo
  "Nessun rischio rilevato" → omettere completamente la sezione
```

### Sezione 6 — Esempi [opzionale ma fortemente consigliato]

Esempi concreti del task. Possono essere:

- **Prima/Dopo**: input e output corrispondente
- **Corretto/Scorretto**: due output dello stesso input, uno conforme alla
  skill e uno no, con spiegazione del perché l'uno funziona e l'altro no

Gli esempi sono **few-shot inline**: il modello li legge e calibra il suo
comportamento su di essi.

Limiti pratici:

- Tra 1 e 3 esempi per skill (più non aiuta, occupa context window)
- Lunghezza totale della sezione: max 400 parole
- Ogni esempio termina con una riga "Perché funziona / perché no"

Le skill v2.0 storiche eccellevano su questo. La v2.5 mantiene la
caratteristica.

### Sezione 7 — Vincoli operativi assoluti (obbligatoria, ~80-150 parole)

Lista numerata di vincoli che il modello deve rispettare a prescindere
da tutto il resto. Sono i vincoli che, se violati, rendono l'output
automaticamente inaccettabile.

Esempio dal `diff_review`:

```markdown
- **Focus sul diff**: non revieware codice non modificato dal diff
- **No estetica sul non-modificato**: niente commenti tipo "anche questa
  funzione qui sopra dovrebbe avere docstring"
- **Severity calibrata**: usa `critical` solo per rischi con impatto
  immediato. Non gonfiare i severity.
- **Identificazione "pubblico" tracciabile**: ogni breaking change cita
  il dato del context che giustifica la qualifica
```

Differenza con la sezione 4: la sezione 4 dice **cosa fare**, la sezione 7
dice **cosa non fare mai** (anche se altre istruzioni nel prompt lo
suggerissero).

### Sezione 8 — Self-check criteria (obbligatoria)

I criteri che il self-check del BaseAgent applica alla bozza prima di
restituirla. Devono essere coerenti con `self_check_persona` dichiarata
nel frontmatter.

Struttura:

```markdown
## 8. Self-check criteria

Quando valuti la tua bozza, applica questi criteri con default conservativo
(preferisci bloccare un problema potenziale piuttosto che lasciarlo passare):

- **<Criterio 1>**: <domanda di verifica>
- **<Criterio 2>**: <domanda di verifica>
- ...

### Severity assignment

- `critical`: <cosa rende il problema critico>
- `high`: <cosa rende il problema alto>
- `medium`: <cosa rende il problema medio>
- `low`: <cosa rende il problema basso>
```

Le skill v2.0 hanno questa sezione come "Checklist self-verifica" con
lista `[ ]`. Mantenere il formato bullet, ma aggiungere la severity
assignment esplicita (dalle skill B).

### Sezione 9 — Rubrica deterministica del quality_score (obbligatoria)

Il `quality_score` finale prodotto dal self-check è la media pesata di N
criteri (tipicamente 4). Pesi che sommano a 1.0.

Struttura standard:

```markdown
## 9. Rubrica deterministica del quality_score

Il quality_score finale e' la media pesata di quattro criteri, ciascuno
valutato da 0.0 a 1.0:

- **<Criterio 1>** (peso 0.30): <descrizione>
- **<Criterio 2>** (peso 0.25): <descrizione>
- **<Criterio 3>** (peso 0.25): <descrizione>
- **<Criterio 4>** (peso 0.20): <descrizione>

Soglia di validita': quality_score < 0.70 → `is_valid: false`, blocca
l'output.
```

I pesi sono a discrezione della skill ma devono sommare a 1.0. La soglia
0.70 è uniforme tra tutte le skill (vincolo di coerenza del sistema).

---

## 5. Stile narrativo: regole prescrittive

Le skill v2.5 sono **prompt prescrittivi**, non documenti tecnici neutri.
Lo stile deve riflettere questa natura.

**Usa frasi nette, non qualificatori vaghi.**

NO: "Sarebbe consigliabile, se possibile, considerare la verifica dei casi
limite."

SI: "Verifica sempre i casi limite. None, lista vuota, stringa vuota, file
non trovato."

**Usa la seconda persona singolare per istruire il modello.**

NO: "Il modello dovrebbe rifiutare le review generiche."

SI: "Non scrivere review generiche. Una review che dice 'il codice presenta
alcuni problemi' senza specificarli e' una review non fatta."

**Anticipa il fallimento, neutralizzalo prima che accada.**

I modelli hanno bias noti: eccesso di gentilezza, vaghezza, omissione di
dettagli scomodi. Le skill devono nominare questi bias e correggerli
preventivamente.

Esempio dal `code_review`:

> Una review che trova zero problemi su codice non triviale e' quasi sempre
> una review non fatta bene.

Questa frase non descrive una regola tecnica. Descrive una **tendenza** del
modello e la neutralizza.

**Quando un vincolo è assoluto, dillo esplicitamente.**

NO: "È preferibile evitare di catturare eccezioni generiche."

SI: "PROIBITO: `except Exception:` che cattura tutto. Questa pratica nasconde
i bug. Usa sempre eccezioni specifiche."

**Mantieni il tono italiano professionale.**

Tutte le skill esistenti sono in italiano. La nuova standard mantiene la
convenzione. Termini tecnici Python (type hint, fixture, monkeypatch) restano
in inglese.

---

## 6. Esempi nel corpo

Le skill v2.5 includono esempi concreti nella sezione 6 perché sono
**few-shot**: il modello li legge e calibra il suo comportamento.

### Pattern "Prima / Dopo"

Per skill che producono modifiche al codice (`refactor`, `python_generation`):

```markdown
**PRIMA** (problema da correggere):

```python
def get_data(source, use_cache):
    if use_cache:
        return _from_cache(source)
    return _from_network(source)
```

**DOPO** (forma corretta):

```python
def get_data_cached(source: str) -> Data:
    """Recupera dati dalla cache locale."""
    return _from_cache(source)

def get_data_fresh(source: str) -> Data:
    """Recupera dati freschi dalla rete."""
    return _from_network(source)
```

**Perché**: il parametro booleano è un boolean trap. La funzione fa due cose
diverse a seconda del flag. Due funzioni separate sono più chiare e
testabili.
```

### Pattern "Corretto / Scorretto"

Per skill che producono prosa (`code_review`, `diff_review`,
`documentation`):

```markdown
**Output scorretto** (non fare così):

> ## Sommario
> Il codice funziona ma potrebbe essere migliorato in alcuni punti.

**Perché è scorretto**: il sommario è vago, non riflette problemi reali,
non e' azionabile.

**Output corretto** (fai così):

> ## Sommario
> Il codice ha due problemi critici: deserializzazione non sicura con
> yaml.load e soppressione silenziosa di tutti gli errori con except nudo.

**Perché funziona**: il sommario nomina problemi specifici, indica la
severity (critici), e' azionabile.
```

---

## 7. Self-check e rubrica deterministica

La rubrica deterministica del `quality_score` (sezione 9 della skill) è
la differenza tra una skill che produce output coerenti e una che produce
output erratici.

**Principi della rubrica:**

1. **Pesi espliciti**: 4 criteri, pesi che sommano a 1.0
2. **Criteri valutabili**: ogni criterio deve essere valutabile su una scala
   0.0-1.0 leggendo l'output. Niente criteri vaghi tipo "qualità generale".
3. **Soglia uniforme**: 0.70 è la soglia di validità per tutte le skill
4. **Coerenza con self-check criteria** (sezione 8): i criteri della
   rubrica devono mappare sui criteri del self-check

**Esempio di rubrica ben fatta** (da `diff_review`):

- **Focus sul diff** (peso 0.30): la review parla dei cambiamenti, non
  del codice esistente
- **Concretezza** (peso 0.25): ogni osservazione cita file/righe; ogni
  suggerimento è azionabile
- **Calibrazione severity** (peso 0.25): severity giustificati dall'impatto,
  distinzione corretta tra regressione e breaking change
- **Strutturazione formale** (peso 0.20): sezioni obbligatorie presenti,
  condizionali correttamente incluse/omesse

**Esempio di rubrica mal fatta** (da evitare):

- Qualità del codice (peso 0.50): è di buona qualità?
- Completezza (peso 0.50): è completo?

Il problema: "buona qualità" e "completo" non sono valutabili in modo
deterministico. La rubrica diventa soggettiva e il `quality_score` perde
significato.

---

## 8. Anti-pattern (cosa non fare)

### Anti-pattern 1: skill puramente descrittiva

Una skill che si limita a elencare le caratteristiche del task senza
prescrivere il comportamento. Esempio:

> Questo task riguarda la review del codice Python. Il modello dovrebbe
> analizzare il codice e fornire feedback.

**Perché è male**: il modello non sa COME fare review. Quale severità usare,
in che ordine analizzare, cosa includere, cosa omettere.

**Cosa fare invece**: ogni skill è **prescrittiva**. Dice al modello come
pensare e cosa produrre, con regole nette.

### Anti-pattern 2: frontmatter con slug senza testo espanso

Frontmatter che dichiara `self_check_persona: adversarial` senza
`_persona_text` corrispondente.

**Perché è male**: lo slug è un identificatore opaco. Il modello e l'umano
non sanno cosa significa concretamente. Il sistema oggi non parsa lo slug,
quindi non viene mai trasformato in un prompt operativo.

**Cosa fare invece**: ogni slug pragmatico ha un campo `_<nome>_text`
con la versione espansa che il modello legge oggi e che il sistema
configurazionale userà domani.

### Anti-pattern 3: sezioni condizionali con disclaimer vuoti

Sezione `## Rischi` con contenuto "Nessun rischio rilevato".

**Perché è male**: occupa context window, comunica zero informazione, è il
tipo di filler che il modello produce di default.

**Cosa fare invece**: sezioni condizionali si **omettono** quando non hanno
contenuto. La skill deve dirlo esplicitamente nella sezione 5.

### Anti-pattern 4: dati del context non dichiarati

Skill che usa nel suo prompt finale campi del context (es.
`semantic_context.functions`) senza averli dichiarati nella sezione 3.

**Perché è male**: rende impossibile capire cosa la skill richiede al
sistema, e quando il sistema non produce quel dato la skill fallisce in
modo opaco.

**Cosa fare invece**: ogni campo del context usato dalla skill è dichiarato
nella sezione 3, con la sua classificazione Layer 3 vs Layer 4 e con la
regola degradata se opzionale.

### Anti-pattern 5: postura debole

Sezione 2 (Postura) che dice "fai del tuo meglio" o "produci un buon
output".

**Perché è male**: non modella il comportamento, non anticipa fallimenti,
non guida la postura mentale del modello.

**Cosa fare invece**: la sezione 2 è prescrittiva e nomina i bias del
modello. "Il tuo default è BLOCCARE", non "fai il tuo meglio".

### Anti-pattern 6: rubrica vaga

Vedi sezione 7 di questo documento.

### Anti-pattern 7: lunghezza eccessiva

Skill da 3000+ parole. Diluisce il segnale, occupa context window,
diminuisce l'efficacia del modello (lost-in-the-middle).

**Target di lunghezza**:

- Skill compatte (`documentation`, `pytest_generation` semplice): 800-1500
  parole
- Skill medie (`code_review`, `diff_review`): 1500-2500 parole
- Skill grandi (`refactor`, `python_generation`): 2500-3500 parole
- Limite assoluto: 4000 parole

`project_rules` è un caso speciale (iniettata in ogni task, deve essere
compatta): target 1500 parole.

---

## 9. Checklist di conformità

Prima di considerare una skill v2.5 completa, verifica:

### Frontmatter
- [ ] `name` corrisponde alla cartella
- [ ] `version: 2.5`
- [ ] `applies_to` lista i task corretti
- [ ] `priority` numerico, coerente con la convenzione
- [ ] `inject_position` esplicito (`first`, `middle`, o `last`)
- [ ] `max_output_words` numerico o `"unlimited"`
- [ ] `conflict_resolution` slug + `_conflict_resolution_text` espanso
- [ ] `self_check_persona` slug + `_persona_text` espanso
- [ ] `description` presente (3-5 righe)

### Struttura del corpo
- [ ] Le 9 sezioni canoniche sono presenti nell'ordine giusto
- [ ] Sezione 1 (Scopo): 2-4 frasi, no implementazione
- [ ] Sezione 2 (Postura): narrativa, prescrittiva, ~100-200 parole
- [ ] Sezione 3 (Dati del context): Layer 3 e Layer 4 distinti
- [ ] Sezione 3 (Dati del context): opzionali con regola degradata
- [ ] Sezione 4 (Regole operative): prescrittive con esempi
- [ ] Sezione 5 (Formato output): vincoli espliciti
- [ ] Sezione 6 (Esempi): almeno 1, max 3, "Perché" alla fine
- [ ] Sezione 7 (Vincoli assoluti): 3-6 vincoli numerati
- [ ] Sezione 8 (Self-check): criteri + severity assignment
- [ ] Sezione 9 (Rubrica): 4 criteri con pesi che sommano a 1.0, soglia 0.70

### Stile
- [ ] Frasi nette, no qualificatori vaghi
- [ ] Seconda persona singolare per istruire il modello
- [ ] Anti-pattern nominati e neutralizzati
- [ ] Tono italiano professionale
- [ ] Lunghezza totale entro i target

### Anti-pattern evitati
- [ ] No skill puramente descrittiva
- [ ] No slug senza testo espanso
- [ ] No sezioni condizionali con disclaimer vuoti
- [ ] No campi del context non dichiarati
- [ ] No postura debole
- [ ] No rubrica vaga
- [ ] Lunghezza entro i limiti

---

## 10. Esempio canonical minimo

Esempio minimale di skill v2.5 ben formata. Usalo come template per nuove
skill o per migrare quelle esistenti.

```markdown
---
name: example_skill
version: 2.5
applies_to: [example_task]
priority: 80
inject_position: middle
max_output_words: 1000
conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  In caso di conflitto con project_rules, project_rules ha sempre precedenza.
  Le regole di questa skill cedono il passo quando si sovrappongono.
self_check_persona: adversarial
_persona_text: >
  Sei un reviewer esterno. Il tuo default e' bloccare. Cerca attivamente
  motivi per non approvare la bozza dell'agent.
description: >
  Skill di esempio che mostra la struttura canonical v2.5. Da usare come
  template per nuove skill. Non e' registrata nel sistema, e' solo un
  riferimento.
---

# example_skill v2.5

## 1. Scopo della skill

Eseguire il task X producendo output Y. La skill privilegia <proprietà 1>
su <proprietà 2>. Si distingue da <skill_simile> perche' <ragione>.

## 2. Postura (come pensare al task)

Non stai facendo X per esercitare la tua creatività. Stai facendo X per
produrre un risultato che <criterio concreto>.

Il tuo default e': <postura forte>. Anticipa la tendenza del modello a
<bias 1>. Anticipa la tendenza del modello a <bias 2>.

Una bozza che <pattern di fallimento> e' quasi sempre una bozza non ben fatta.

## 3. Dati del context utilizzati

### Reference (Layer 3, stabile tra run)
- `project_rules` (sempre presente)

### Working artifacts (Layer 4, specifico al run)
- `task.raw_input` — <descrizione>
- `semantic_context.functions` — <descrizione>

### Opzionali (versioni future)
- `<campo_futuro>` — non ancora prodotto. Se assente, applica la regola
  degradata: <descrizione>.

## 4. Regole operative

### 4.1 <Aspetto 1>

<Regola prescrittiva concreta>

### 4.2 <Aspetto 2>

<Regola prescrittiva concreta>

## 5. Formato dell'output

L'output e' <prosa markdown | codice Python | altro>.

Sezioni obbligatorie:
- `## <Sezione 1>` (sempre, max N parole)
- `## <Sezione 2>` (sempre, max N parole)

Sezioni condizionali (incluse SOLO se hanno contenuto reale):
- `## <Sezione X>` (max N parole)

Vietato:
- <vincolo formale 1>
- <vincolo formale 2>

## 6. Esempi

**Output scorretto** (non fare così):

<esempio scorretto>

**Perché è scorretto**: <spiegazione>

**Output corretto** (fai così):

<esempio corretto>

**Perché funziona**: <spiegazione>

## 7. Vincoli operativi assoluti

- **<Vincolo 1>**: <descrizione>
- **<Vincolo 2>**: <descrizione>
- **<Vincolo 3>**: <descrizione>

## 8. Self-check criteria

Quando valuti la tua bozza, applica questi criteri con default conservativo:

- **<Criterio 1>**: <domanda di verifica>
- **<Criterio 2>**: <domanda di verifica>
- **<Criterio 3>**: <domanda di verifica>
- **<Criterio 4>**: <domanda di verifica>

### Severity assignment

- `critical`: <cosa rende il problema critico>
- `high`: <cosa rende il problema alto>
- `medium`: <cosa rende il problema medio>
- `low`: <cosa rende il problema basso>

## 9. Rubrica deterministica del quality_score

Il quality_score finale e' la media pesata di quattro criteri:

- **<Criterio 1>** (peso 0.30): <descrizione>
- **<Criterio 2>** (peso 0.25): <descrizione>
- **<Criterio 3>** (peso 0.25): <descrizione>
- **<Criterio 4>** (peso 0.20): <descrizione>

Soglia di validità: quality_score < 0.70 → `is_valid: false`, blocca l'output.
```

---

## Note sulla migrazione delle skill esistenti (v2.0 → v2.5)

Le 5 skill v2.0 storiche (`project_rules`, `code_review`, `python_generation`,
`refactor`, `documentation`) sono state migrate al formato v2.5 nella v0.2.0
di Assist CLI. Le 3 skill aggiunte successivamente (`diff_review`,
`pytest_generation`, `repository_overview`) sono nate direttamente v2.5.

Stato a fine v0.2.0: **8 skill in formato v2.5**, nessuna v2.0 residua.

---

# Parte II — Estensione v3.0: Runtime Configuration

> Da Assist CLI v0.3.0, il formato delle skill viene esteso con campi
> **opzionali** che il `SkillResolver` parsa al caricamento e che il
> sistema usa a runtime per dispatch, validazione e routing automatico.
>
> Le skill v2.5 esistenti **continuano a funzionare invariate**.
> L'adozione di v3.0 è opt-in, skill per skill.

---

## 11. Motivazione e ambito v3.0

### 11.1 Il problema che v3.0 risolve

Nel formato v2.5, il frontmatter dichiara molti aspetti del comportamento
della skill (`max_output_words`, `self_check_persona`, `conflict_resolution`,
`inject_position`). Tuttavia, **il `SkillResolver` carica la skill come
stringa raw** senza parsare questi campi. Tutto il parsing del frontmatter
avviene altrove (nel `PromptBuilder` o negli `Agent` specifici), in modo
disomogeneo:

- Alcuni campi sono letti, altri ignorati a runtime
- Ogni Agent specializzato (`ReviewerAgent`, `RefactorAgent`, ecc.) sa
  implicitamente cosa aspettarsi dall'output della propria skill, ma
  questa conoscenza è hardcoded nel codice, non dichiarata nella skill
- Il `PromptBuilder` ha 24 metodi `build_<task>_prompt` paralleli, ognuno
  con piccole differenze, perché non c'è un modo dichiarativo di descrivere
  "questo task produce prose con N sezioni, questo altro produce codice
  Python puro"

Il risultato: le skill dichiarano comportamento nel frontmatter (per umani
e LLM che leggono), ma il **codice non usa quelle dichiarazioni**. Sono
documentazione, non configurazione.

### 11.2 L'obiettivo di v3.0

Trasformare il frontmatter da **documentale** a **runtime**: i campi nuovi
sono parsati dal `SkillResolver`, validati con Pydantic, e accessibili al
sistema per:

- **Dispatch automatico**: il sistema sa che `code_review` produce prose,
  `python_generation` produce codice, `repository_overview` produce
  un'analisi strutturata. Niente più Agent specializzati hardcoded.
- **Validazione anticipata**: se una skill dichiara di richiedere
  `semantic_context.functions` e il sistema non lo produce, errore chiaro
  al caricamento, non a runtime.
- **Routing verifier**: il `GlobalVerifier` sa quali check applicare
  (AST parse vs section headers vs nessuno) leggendo la skill, non
  hardcoded per task.
- **Prompt builder dichiarativo**: il `PromptBuilder` sa dove iniettare
  reference (Layer 3) e working artifacts (Layer 4) leggendo le
  dichiarazioni della skill.

### 11.3 Cosa NON è incluso in v3.0

Per non gonfiare lo scope dell'estensione, **NON** sono parte di v3.0:

- **Prompt template inline nelle skill**: i template del prompt finale
  restano nel `PromptBuilder`. La v3.0 dichiara cosa la skill richiede
  e produce, non come il prompt finale viene costruito. Una v3.1+ potrà
  spostare i template dentro le skill.
- **Variabili template con sostituzione**: niente `{file_content}` o
  `{static_analysis}` parsati dalle skill. Coerente con il punto sopra.
- **Verifier custom completi**: solo modi predefiniti (`noop`, `ast`,
  `section_headers`, `rubric`). Verifier personalizzati per skill specifica
  arriveranno in versioni successive.
- **Configurazione di provider LLM per skill**: una skill non può
  dichiarare "io preferisco GPT-4 per questa cosa". Provider è una
  decisione di sistema, non di skill.

### 11.4 Principio guida

**v3.0 è additiva**. Aggiunge campi al frontmatter, **non rimuove** né
**modifica** campi v2.5. Una skill v2.5 valida è anche una skill v3.0
valida con campi runtime omessi (default applicato).

---

## 12. Frontmatter v3.0 (campi aggiuntivi)

Le skill v3.0 aggiungono al frontmatter v2.5 i seguenti **5 gruppi di
campi**, tutti **opzionali singolarmente** ma **fortemente consigliati**:

```yaml
---
# Campi v2.5 invariati
name: code_review
version: 3.0                  # bumped da 2.5
applies_to: [review]
priority: 80
inject_position: middle
max_output_words: 300
conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  ...
self_check_persona: adversarial
_persona_text: >
  ...
description: >
  ...

# NUOVI campi v3.0
task_type: prose

inputs:
  required:
    - raw_input
  optional:
    - options

outputs:
  format: markdown
  sections:
    required:
      - "## Sommario"
      - "## Problemi critici"
      - "## Problemi significativi"
    optional:
      - "## Suggerimenti"

process:
  max_corrections: 1
  quality_threshold: 0.70

verifier:
  syntax: noop
  format: section_headers
  coherence: rubric
---
```

### 12.1 Campo `task_type` (obbligatorio in v3.0)

Tipo di output prodotto dalla skill. Valori validi:

- **`prose`**: output è testo markdown strutturato (esempi: `code_review`,
  `diff_review`, `documentation`, `repository_overview`)
- **`code`**: output è codice puro (esempi: `python_generation`,
  `pytest_generation`)
- **`json`**: output è JSON valido (riservato per skill future che
  producono dati strutturati)

Il sistema usa `task_type` per:
- Scegliere il verifier appropriato (es. AST parse solo se `code`)
- Calibrare `max_tokens` di default (prose: 4000, code: 8000, json: 2000)
- Determinare il rendering nell'`OutputFormatter`

### 12.2 Campo `inputs` (opzionale ma raccomandato)

Dichiarazione dichiarativa dei dati del context che la skill richiede.

```yaml
inputs:
  required:
    - <nome_campo>
    - <nome_campo>
  optional:
    - <nome_campo>
```

I valori sono nomi di campi del `PromptContext` (vedi `models.py`),
oppure campi della task (es. `raw_input`, `options`, `file_path`).

**Validazione**: al caricamento della skill, il sistema verifica:
- Tutti i campi in `required` esistono nel `PromptContext`
- I campi in `optional` esistono (o sono campi noti `_futuri`)
- Nessun campo non-conosciuto

Errore chiaro al boot se una skill richiede un campo che il sistema non
produce. Niente più fallimenti opachi a runtime.

**Coerenza con sezione 3 del body**: i campi qui dichiarati sono lo **slug
parsabile** della sezione 3 (Dati del context utilizzati) del body markdown.
Devono coincidere. La sezione 3 resta umano-leggibile, il frontmatter è
parsato.

### 12.3 Campo `outputs` (opzionale ma raccomandato)

Struttura dell'output prodotto dalla skill.

```yaml
outputs:
  format: <markdown | python | json>
  sections:           # solo se format == markdown
    required:
      - "## Sezione 1"
      - "## Sezione 2"
    optional:
      - "## Sezione X"
```

**`format`**: deve essere coerente con `task_type`. Combinazioni valide:
- `task_type: prose` → `format: markdown`
- `task_type: code` → `format: python` (o `format: typescript`, ecc.)
- `task_type: json` → `format: json`

**`sections`**: solo per `format: markdown`. Lista di sezioni che il
verifier verifica nell'output. Le sezioni `required` devono essere presenti;
le `optional` possono apparire o no.

Il `GlobalVerifier` userà `sections.required` per il check `format` se
`verifier.format: section_headers`.

### 12.4 Campo `process` (opzionale)

Parametri del loop di esecuzione del BaseAgent.

```yaml
process:
  max_corrections: <int>
  quality_threshold: <float>
```

**`max_corrections`** (int, default 1): numero massimo di iterazioni
`generate_draft → self_check → correct`. Coerente con la convenzione
esistente: prose=1, code=2.

**`quality_threshold`** (float, default 0.70): soglia sotto la quale
`is_valid: false` blocca l'output. Coerente con la sezione 9 della skill
(rubrica deterministica). Soglia uniforme nel sistema.

### 12.5 Campo `verifier` (opzionale)

Configurazione del `GlobalVerifier` per questa skill.

```yaml
verifier:
  syntax: <noop | ast>
  format: <noop | section_headers>
  coherence: <noop | rubric>
```

**`syntax`**:
- `noop`: nessun check di sintassi (per `task_type: prose`)
- `ast`: il verifier estrae il codice e fa `ast.parse()` (per `task_type:
  code`)

**`format`**:
- `noop`: nessun check di formato
- `section_headers`: il verifier controlla che le sezioni in
  `outputs.sections.required` siano presenti

**`coherence`**:
- `noop`: nessun check di coerenza
- `rubric`: il verifier delega alla rubrica deterministica della sezione 9
  della skill, applicando la `quality_threshold`

**Combinazioni tipiche**:

| task_type | syntax | format | coherence |
|-----------|--------|--------|-----------|
| prose     | noop   | section_headers | rubric |
| code      | ast    | noop            | rubric |
| json      | noop   | noop            | rubric |

### 12.6 Campi futuri (predisposti, non ancora attivi)

I seguenti campi sono **menzionati per riferimento** ma **non attivi** in
v3.0. Le skill possono ometterli senza problemi. Saranno attivati in
versioni successive:

- `provider_hints`: dichiarazione di compatibilità con provider LLM
  specifici (Anthropic, OpenAI, locale via Ollama)
- `cost_class`: indicazione di costo computazionale stimato
- `prompt_template`: template del prompt inline (v3.1+)
- `cache_policy`: gestione cache dei risultati per questa skill (v0.4.0)

---

## 13. Modello Pydantic Skill esteso

Il modello `Skill` in `assist/schemas/models.py` viene esteso con campi
**opzionali tipizzati** che vengono popolati dal `SkillResolver` solo se la
skill è v3.0.

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SkillInputs(BaseModel):
    """Dati del context che la skill richiede."""
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class SkillOutputSections(BaseModel):
    """Sezioni dell'output (solo per format=markdown)."""
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class SkillOutputs(BaseModel):
    """Struttura dell'output prodotto dalla skill."""
    format: Literal["markdown", "python", "json"]
    sections: Optional[SkillOutputSections] = None


class SkillProcess(BaseModel):
    """Parametri del loop di esecuzione."""
    max_corrections: int = Field(default=1, ge=0, le=3)
    quality_threshold: float = Field(default=0.70, ge=0.0, le=1.0)


class SkillVerifier(BaseModel):
    """Configurazione del verifier."""
    syntax: Literal["noop", "ast"] = "noop"
    format: Literal["noop", "section_headers"] = "noop"
    coherence: Literal["noop", "rubric"] = "noop"


class Skill(BaseModel):
    """
    Skill di Assist CLI.

    Campi v2.5 (originali):
    - name, content: invariati. Compatibili con tutte le skill esistenti.

    Campi v3.0 (opzionali):
    - version: "2.5" o "3.0". Default "2.5" per retrocompatibilità.
    - task_type, inputs, outputs, process, verifier: parsati dal frontmatter
      solo se la skill dichiara version: 3.0. Per skill v2.5, restano None.
    """
    name: str
    content: str

    # NUOVI campi v3.0 (opzionali)
    version: str = "2.5"
    task_type: Optional[Literal["prose", "code", "json"]] = None
    inputs: Optional[SkillInputs] = None
    outputs: Optional[SkillOutputs] = None
    process: Optional[SkillProcess] = None
    verifier: Optional[SkillVerifier] = None
```

### 13.1 Comportamento del `SkillResolver`

Il resolver, al caricamento di una skill:

1. Legge il file `SKILL.md`
2. Estrae il frontmatter YAML (tra `---` e `---`)
3. Determina la versione: legge il campo `version` (default `2.5` se assente)
4. Se `version == "2.5"`: popola solo `name` e `content`. Campi v3.0
   restano `None`.
5. Se `version == "3.0"`: parsa anche `task_type`, `inputs`, `outputs`,
   `process`, `verifier`. Valida con Pydantic.
6. Restituisce l'oggetto `Skill` tipizzato.

**Errori al caricamento**:
- Frontmatter YAML malformato → errore chiaro con riga
- Campo `task_type` non riconosciuto → errore con valori validi
- Inconsistenza `task_type` vs `outputs.format` → errore esplicito
- Campo richiesto in `inputs.required` non esistente nel sistema → errore
  con nome del campo

### 13.2 Comportamento del sistema esistente

Il codice esistente che usa `skill.content` (raw text) **continua a
funzionare invariato**. I nuovi campi sono additivi.

Il nuovo codice (Agent generico, PromptBuilder dichiarativo, GlobalVerifier
configurabile) usa i campi v3.0 quando disponibili e fallisce in modo
chiaro se richiede campi v3.0 da una skill v2.5.

---

## 14. Retrocompatibilità e convivenza v2.5 / v3.0

### 14.1 Le 8 skill esistenti restano v2.5

Al rilascio di Assist CLI v0.3.0, le 8 skill esistenti (`project_rules`,
`code_review`, `python_generation`, `refactor`, `documentation`,
`diff_review`, `pytest_generation`, `repository_overview`) **non sono
costrette a migrare**. Restano in v2.5 e funzionano come prima.

La migrazione a v3.0 avviene **una skill per volta**, quando il team decide
di abilitare le funzionalità runtime per quella skill specifica.

**Ordine di migrazione raccomandato** (basato su priorità di impatto):

1. `code_review` — pilota della migrazione (la più usata)
2. `diff_review` — simile a code_review, beneficio diretto
3. `repository_overview` — output strutturato, beneficia di `outputs.sections`
4. `documentation` — simile struttura, basso rischio
5. `python_generation`, `pytest_generation` — `task_type: code`,
   beneficia di verifier `ast`
6. `refactor` — più complessa, migrare per ultima tra le "concrete"
7. `project_rules` — caso speciale (iniettata in ogni task), migrare solo
   dopo aver verificato che tutte le altre funzionino

### 14.2 Tabella di mapping v2.5 → v3.0

Quando si migra una skill, alcuni concetti v2.5 trovano corrispondenti
strutturati in v3.0. Altri restano invariati.

| Concetto v2.5 | Forma v2.5 | Forma v3.0 |
|---------------|------------|------------|
| Nome skill | `name` (frontmatter) | `name` (invariato) |
| Versione | `version: 2.5` | `version: 3.0` |
| Task supportati | `applies_to` | `applies_to` (invariato) |
| Priorità | `priority` | `priority` (invariato) |
| Persona self-check | `self_check_persona` + `_persona_text` | Invariato |
| Conflict resolution | `conflict_resolution` + `_conflict_resolution_text` | Invariato |
| Tipo output (prose vs code) | Implicito nel body sezione 5 | **`task_type`** esplicito |
| Campi context usati | Dichiarati nella sezione 3 (testo) | **`inputs`** strutturato |
| Sezioni output richieste | Dichiarate nella sezione 5 (testo) | **`outputs.sections`** strutturato |
| Soglia quality | Implicita 0.70 (sezione 9) | **`process.quality_threshold`** esplicita |
| Numero correzioni | Hardcoded nel BaseAgent per task | **`process.max_corrections`** esplicito |
| Tipo verifier | Hardcoded nel GlobalVerifier per task | **`verifier`** dichiarativo |

I campi nuovi v3.0 **non sostituiscono** le sezioni descrittive del body
(3, 5, 8, 9). Il body markdown resta come è — è la parte human-readable,
quella che il modello LLM legge. Il frontmatter v3.0 è la parte
machine-readable, parsata dal sistema.

**Una skill v3.0 ben fatta dichiara la stessa cosa in due forme**: il
frontmatter strutturato (per il sistema) e il body narrativo (per
l'umano e per l'LLM). Coerenza tra le due è un requisito.

### 14.3 Convivenza durante la migrazione

Mentre la migrazione procede skill per skill, il sistema gestisce mix
v2.5 / v3.0 in modo trasparente:

- Skill v2.5: codice usa `skill.content` (raw text), inietta nel prompt
  come oggi. Sistema funziona come prima.
- Skill v3.0: codice può usare anche `skill.task_type`, `skill.inputs`,
  ecc. per dispatch intelligente, ma se per qualche motivo non lo fa,
  il fallback è sempre `skill.content` (raw text). Niente regressione.

**Vincolo di transizione**: durante la migrazione, ogni skill deve essere
verificata con uno smoke test reale (eseguire il task con un LLM e
controllare che il quality score non sia regredito rispetto a v2.5).

### 14.4 Validazione di una skill v3.0

Quando una skill dichiara `version: 3.0`, il `SkillResolver` applica
validazioni strict:

- **`task_type` obbligatorio**: senza, errore "v3.0 requires task_type"
- **`outputs.format` coerente con `task_type`**:
  - `prose` ↔ `markdown`
  - `code` ↔ `python` (o altri linguaggi futuri)
  - `json` ↔ `json`
- **`outputs.sections` presente solo se `format: markdown`**
- **`process.quality_threshold` ∈ [0.0, 1.0]**
- **`process.max_corrections` ∈ [0, 3]**
- **`inputs.required` non vuoto** se la skill produce output significativo
  (warning, non errore)
- **Campi v3.0 sconosciuti**: warning con suggerimento (es. "did you mean
  `verifier`?")

Errori al caricamento sono **fatali**: il sistema non parte con skill v3.0
malformate, in modo che problemi siano scoperti al boot, non a runtime.

---

## 15. Esempio: code_review migrata a v3.0

Per illustrare concretamente la migrazione, ecco il frontmatter completo
di `code_review` in versione v3.0. Il body markdown (sezioni 1-9) resta
**identico** alla versione v2.5 esistente.

```yaml
---
# === Campi v2.5 (invariati) ===
name: code_review
version: 3.0                  # ← bumped da 2.5
applies_to: [review]
priority: 80
inject_position: middle
max_output_words: 300
load_examples: false
load_templates: false

conflict_resolution: project_rules_wins
_conflict_resolution_text: >
  In caso di conflitto con project_rules, project_rules ha precedenza.
  Le regole di questa skill cedono il passo su qualsiasi punto in cui
  le due si sovrappongono.

self_check_persona: adversarial
_persona_text: >
  Sei un senior engineer che deve decidere se bloccare un merge in produzione.
  Il tuo default e' BLOCCARE. Cerca attivamente motivi per non approvare.
  Una review che trova zero problemi su codice non triviale e' quasi sempre
  una review non fatta bene.

description: >
  Regole per la review di codice Python. Include scala di severita' calibrata,
  ordine di analisi fisso, persona avversariale per il self-check, formato
  strutturato verificato automaticamente, esempi di review corretta e scorretta.

# === Campi v3.0 (NUOVI, opzionali ma raccomandati) ===

task_type: prose

inputs:
  required:
    - raw_input               # il codice Python da analizzare
  optional:
    - options                 # dict CLI: mode, verbose, ecc.

outputs:
  format: markdown
  sections:
    required:
      - "## Sommario"
      - "## Problemi critici"
      - "## Problemi significativi"
    optional:
      - "## Suggerimenti"

process:
  max_corrections: 1
  quality_threshold: 0.70

verifier:
  syntax: noop                # output prose, niente AST
  format: section_headers     # verifica le tre sezioni obbligatorie
  coherence: rubric           # delega alla rubrica della sezione 9 del body
---

# code_review v3.0

[Body identico a v2.5: sezioni 1-9 invariate.]
```

### 15.1 Cosa cambia in pratica nell'output

Eseguendo `assist review file.py` con la skill `code_review` v3.0:

- **Caricamento**: il `SkillResolver` parsa anche i campi v3.0 e valida.
  Se la skill è malformata, errore chiaro al boot.
- **Prompt**: il `PromptBuilder` (quando refactorato in Epic 1.2) può
  usare `inputs.required` per popolare il context, e `outputs.sections`
  per il template strutturato. Per ora, prima del refactor del
  PromptBuilder, il prompt è costruito come per v2.5 (compat mode).
- **Verifier**: il `GlobalVerifier` legge `skill.verifier` e applica
  `format: section_headers` per verificare le 3 sezioni obbligatorie.
  Niente più hardcoded per task.
- **Score**: la `process.quality_threshold` è applicata. Coerenza con
  la rubrica del body (sezione 9).

Per l'utente finale, **niente cambia**. Il comando `assist review` produce
lo stesso tipo di output. Sotto il cofano, il sistema fa dispatch
dichiarativo invece di hardcoded.

---

## 16. Migrazione: cosa cambia, cosa resta uguale

### 16.1 Cosa cambia nel processo di scrittura di una skill v3.0

Aggiungere a una skill v2.5 esistente i 5 campi v3.0 nel frontmatter:

1. Cambiare `version: 2.5` in `version: 3.0`
2. Aggiungere `task_type: <prose|code|json>`
3. Aggiungere `inputs:` con le liste required/optional
4. Aggiungere `outputs:` con format e sections
5. Aggiungere `process:` con max_corrections e quality_threshold
6. Aggiungere `verifier:` con i 3 modi

**Sforzo per skill**: ~10-15 minuti, mostly mechanical. La maggior parte
delle informazioni è già nel body della skill v2.5 (sezione 3 per inputs,
sezione 5 per outputs, sezione 9 per quality_threshold). Trasferirle nel
frontmatter è copia-incolla riformattato.

### 16.2 Cosa NON cambia

- **Body markdown**: le 9 sezioni canoniche restano invariate. Niente
  riscritture. v3.0 è **additiva al frontmatter**, non al body.
- **Stile e tono**: italiano professionale, prescrittivo, anti-bias.
  Tutto il lavoro fatto sul tono v2.5 è preservato.
- **Esempi nel corpo**: la sezione 6 resta come è, è "few-shot inline"
  che il modello legge a runtime.
- **Rubrica deterministica**: la sezione 9 resta. Il `verifier.coherence:
  rubric` si **basa** su quella sezione, non la sostituisce.

### 16.3 Vincolo di coerenza body ↔ frontmatter

Quando una skill v3.0 dichiara qualcosa nel frontmatter, **deve essere
coerente** con quanto dichiarato nel body:

| Frontmatter v3.0 | Body markdown |
|------------------|---------------|
| `inputs.required` | Devono apparire nella sezione 3 (Reference + Working) |
| `outputs.format` | Coerente con la sezione 5 (Formato output) |
| `outputs.sections.required` | Le stesse sezioni dichiarate nella sezione 5 |
| `process.quality_threshold` | Coerente con la sezione 9 (Rubrica) |
| `verifier.coherence: rubric` | Implica che la sezione 9 sia presente e ben formata |

**Validazione automatica**: il `SkillResolver` non verifica questa coerenza
(richiederebbe parsing del body). È **responsabilità dell'autore della
skill** mantenere la coerenza. La checklist v3.0 (sezione 17) include
questo come passaggio obbligatorio.

---

## 17. Checklist v3.0

Prima di considerare una skill v3.0 completa, oltre alla checklist v2.5
(sezione 9 di questo documento), verifica:

### Frontmatter v3.0
- [ ] `version: 3.0` esplicito
- [ ] `task_type` presente e valido (`prose`, `code`, `json`)
- [ ] `inputs.required` lista i campi del context realmente usati
- [ ] `inputs.optional` lista i campi che, se presenti, migliorano l'output
- [ ] `outputs.format` coerente con `task_type` (prose→markdown, ecc.)
- [ ] `outputs.sections.required` presente solo se `format: markdown`,
      coincide con le sezioni obbligatorie del body sezione 5
- [ ] `process.max_corrections` numerico (0-3)
- [ ] `process.quality_threshold` numerico (0.0-1.0)
- [ ] `verifier.syntax` valido (`noop` o `ast`)
- [ ] `verifier.format` valido (`noop` o `section_headers`)
- [ ] `verifier.coherence` valido (`noop` o `rubric`)

### Coerenza body ↔ frontmatter
- [ ] I campi in `inputs.required` appaiono nella sezione 3 del body
- [ ] Le sezioni in `outputs.sections.required` appaiono nella sezione 5
      del body con vincoli e word limit
- [ ] La sezione 9 del body produce un quality score coerente con
      `process.quality_threshold`
- [ ] Se `verifier.coherence: rubric`, la sezione 9 è presente con 4 criteri
      pesati che sommano a 1.0

### Validazione tecnica
- [ ] La skill carica senza errori con `SkillResolver` (smoke test)
- [ ] Le 8 skill esistenti continuano a caricare (non regressione)
- [ ] Test unit di `test_skill_resolver.py` aggiornati e verdi
- [ ] Smoke test reale: `assist <task> <input>` produce output con
      quality_score ≥ baseline v2.5

### Stato di migrazione
- [ ] Skill aggiunta alla tabella di tracking (se esiste in TECH_DEBT
      o ROADMAP)
- [ ] Commit dedicato: `feat(skills): migrate <name> to v3.0 frontmatter`
- [ ] Nessuna altra skill toccata nello stesso commit (atomic migration)

---

## Note di chiusura — Parte II

La v3.0 dell'estensione Runtime Configuration è il primo passo verso il
**sistema configurazionale completo** previsto per la roadmap v0.3.0
di Assist CLI: un agente generico che legge il comportamento dalla skill
invece di averlo hardcoded in 7 sottoclassi.

Questa specifica copre il **formato delle skill**. Il resto del refactor
(PromptBuilder dichiarativo, Agent generico, TaskTarget tipizzato) è
descritto in `docs/ROADMAP_v0.3.0.md`, Epic 1 e Epic 2.

Una volta che tutte e 8 le skill saranno migrate a v3.0 (target: fine
v0.3.0), v2.5 sarà ufficialmente deprecato (ma sempre supportato per
compatibilità). v3.1 e successive potranno introdurre funzionalità
costruite sopra v3.0:

- **Skill discovery dinamica**: drop di SKILL.md → comando disponibile auto
- **Prompt template inline**: il prompt finale è dichiarato nella skill
- **Provider hints**: skill che dichiarano compatibilità con LLM specifici
- **Workflow composition**: sequenze ordinate di skill in WORKFLOW.md

Tutte queste evoluzioni sono **possibili grazie a v3.0**. Senza i campi
parsati del frontmatter, ognuna richiederebbe un secondo refactor.

---

**Fine specifica SKILL_FORMAT.md** (Parte I v2.5 + Parte II v3.0)
