"""Prompt templates for the 21 PromptBuilder methods.

Each task supports 3 stages: draft, self_check, correct.
Templates use str.format() placeholders. Variables passed by PromptBuilder.

Placeholders used across templates:
- {skills_block}        : concatenated skill contents
- {rendered_context}    : structural context block (PromptContextBuilder)
- {raw_input}           : original code/diff/text from TaskInput
- {draft}               : previously generated draft (self_check, correct)
- {report_json}         : ValidationReport serialized as JSON (correct only)
- {language}            : task.language or "python"
- {language_upper}      : language.upper() — used in headers
- {validation_schema}   : JSON schema block for self_check responses
- {depth}               : explain depth (brief | full)
- {range_spec}          : git range for diff tasks
- {impacted_files_block}: rendered impacted files for diff draft
- {generation_request}  : generation specification for generate draft
- {repo_path}           : repo target path for repo tasks

The dict structure is TEMPLATES[command][stage] -> template string.
"""

from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    # ────────────────────────────────────────────────────────────────
    # REVIEW
    # ────────────────────────────────────────────────────────────────
    "review": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per ancorare la review
a fatti rilevati nel progetto, non a impressioni generiche.

{rendered_context}

# CODICE DA ANALIZZARE

```python
{raw_input}
```

# ESEGUI ORA LA REVIEW

Applica le regole definite nelle skill sopra.

Produci l'output nel formato esatto richiesto
da code_review e project_rules.

Inizia con "## Sommario".

Non aggiungere prefazioni.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# REVIEW DA VALIDARE

{draft}

# VALIDAZIONE

Sei il reviewer finale.

Il tuo compito è bloccare il merge se la review
non è sufficientemente rigorosa, concreta o conforme
alle skill.

Valuta:

- correttezza tecnica
- chiarezza
- conformità al formato richiesto
- presenza di fix concreti
- coerenza con il contesto strutturale

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# REVIEW DA CORREGGERE

{draft}

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi la review usando il validation report.

Mantieni rigorosamente il formato richiesto
da code_review e project_rules.

La review finale deve:

- iniziare con "## Sommario"
- contenere fix concreti
- essere coerente con il contesto strutturale
- non contenere prefazioni
- non contenere spiegazioni meta

Restituisci SOLO la review finale.""",
    },

    # ────────────────────────────────────────────────────────────────
    # GENERATE
    # ────────────────────────────────────────────────────────────────
    "generate": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per ancorare la generazione
a fatti rilevati nel progetto, non a idee astratte.

{rendered_context}

# SPECIFICA DI GENERAZIONE

{generation_request}

# VINCOLI DI OUTPUT

Genera SOLO codice {language} valido.

REGOLE OBBLIGATORIE:
- non aggiungere spiegazioni
- non usare markdown fences
- non aggiungere prefazioni
- non aggiungere testo fuori dal codice
- il risultato deve essere pronto per essere parsato come codice

Se il task richiede un file o un modulo, restituisci direttamente
il contenuto completo del file.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE {language_upper} GENERATO DA VALIDARE

```{language}
{draft}
```

# VALIDAZIONE

Sei il reviewer finale del codice generato.

Valuta il draft rispetto alle skill e al contesto strutturale.

Verifica in particolare:
- sintassi {language} valida
- conformita alle skill (type hints, docstring, naming, lunghezza funzioni)
- assenza di placeholder (TODO, FIXME, pass non intenzionale)
- coerenza con il contesto del progetto

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE DA CORREGGERE

```{language}
{draft}
```

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi il codice usando il validation report.

REGOLE OBBLIGATORIE:
- restituisci SOLO codice {language} valido
- non aggiungere spiegazioni
- non usare markdown fences nell'output finale
- non aggiungere testo fuori dal codice
- il risultato deve essere sintatticamente valido
- il risultato deve essere coerente con le skill
- mantieni le parti del draft che il report non ha segnalato""",
    },

    # ────────────────────────────────────────────────────────────────
    # REFACTOR
    # ────────────────────────────────────────────────────────────────
    "refactor": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per identificare quali
anti-pattern reali sono presenti, non per inventare problemi.

{rendered_context}

# CODICE DA REFACTORIZZARE

```{language}
{raw_input}
```

# ESEGUI ORA IL REFACTORING

Applica le regole definite nelle skill sopra.

VINCOLO ASSOLUTO:
Il refactoring NON cambia il comportamento osservabile del codice.
Stesso output per stesso input. Stesse eccezioni sugli stessi
input errati. Stessi side effect nello stesso ordine.

PROTOCOLLO BUG:
Se trovi un bug nel codice originale, NON correggerlo.
Mantieni il comportamento buggy nel refactoring.
Segnala il bug nella sezione "## Note" del formato output.

Produci l'output nel formato esatto definito dalla skill refactor:
- "## Modifiche apportate" con elenco dei pattern applicati
- "## Codice refactorizzato" con il codice completo in un blocco ```{language}
- "## Note" (opzionale) per bug trovati o breaking change consapevoli

Non aggiungere prefazioni.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE ORIGINALE

```{language}
{raw_input}
```

# REFACTORING PROPOSTO DA VALIDARE

{draft}

# VALIDAZIONE

Sei il reviewer finale del refactoring.

Il tuo default è BLOCCARE. Cerca attivamente motivi per non approvare.

Verifica in particolare:
- INVARIANTE COMPORTAMENTALE: il codice refactorizzato produce lo
  stesso output dell'originale sugli stessi input? Stesse eccezioni?
  Stessi side effect?
- BUG SILENZIATI: il refactoring ha corretto silenziosamente un bug
  dell'originale senza segnalarlo in "## Note"? Se sì, severity high.
- CONFORMITA SKILL: il refactoring segue i pattern definiti nella
  skill refactor (Extract Method, guard clause, dependency injection,
  no magic number)?
- FORMATO: l'output contiene "## Modifiche apportate" e
  "## Codice refactorizzato"? Le note ci sono se ci sono bug?
- SINTASSI: il codice nel blocco "## Codice refactorizzato" e' {language}
  sintatticamente valido?

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE ORIGINALE

```{language}
{raw_input}
```

# REFACTORING DA CORREGGERE

{draft}

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi il refactoring usando il validation report.

REGOLE OBBLIGATORIE:
- mantieni l'INVARIANTE COMPORTAMENTALE rispetto al codice originale
- se il report segnala un bug silenziato, ripristina il comportamento
  originale e sposta la segnalazione in "## Note"
- mantieni il formato richiesto dalla skill refactor:
  "## Modifiche apportate" + "## Codice refactorizzato" + "## Note" (opzionale)
- il blocco "## Codice refactorizzato" deve contenere {language} valido
- mantieni le parti del draft che il report non ha segnalato
- non aggiungere prefazioni
- non aggiungere spiegazioni meta

Restituisci SOLO l'output corretto nel formato definito.""",
    },

    # ────────────────────────────────────────────────────────────────
    # EXPLAIN
    # ────────────────────────────────────────────────────────────────
    "explain": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per spiegare il codice
in modo concreto, ancorato a fatti rilevati nel progetto,
non a impressioni generiche.

{rendered_context}

# CODICE DA SPIEGARE

```{language}
{raw_input}
```

# ESEGUI ORA LA SPIEGAZIONE

Applica le regole definite nelle skill sopra.

Profondita richiesta: {depth}

La spiegazione deve coprire:
- scopo del file
- struttura generale
- funzioni e responsabilita principali
- dipendenze rilevanti
- eventuali criticita o pattern degni di nota
- relazione con il contesto strutturale del progetto

Produci l'output nel formato esatto richiesto dalla skill
documentation. Inizia con "## Sommario".

Non aggiungere prefazioni.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# SPIEGAZIONE DA VALIDARE

{draft}

# VALIDAZIONE

Sei il reviewer finale della spiegazione.

Il tuo compito e' bloccare la pubblicazione se la spiegazione
non e' sufficientemente accurata, chiara o conforme alle skill.

Valuta in particolare:
- accuratezza tecnica rispetto al codice originale
- chiarezza didattica e progressione logica
- completezza (scopo, struttura, dipendenze, criticita)
- coerenza con il contesto strutturale del progetto
- conformita al formato richiesto dalla skill documentation
- assenza di prefazioni o postfazioni
- assenza di ripetizione del codice senza valore aggiunto

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# SPIEGAZIONE DA CORREGGERE

{draft}

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi la spiegazione usando il validation report.

Mantieni rigorosamente il formato richiesto dalla skill
documentation e da project_rules.

La spiegazione finale deve:

- iniziare con "## Sommario"
- essere accurata rispetto al codice originale
- essere coerente con il contesto strutturale
- non contenere prefazioni o postfazioni
- non contenere spiegazioni meta su cosa hai corretto
- mantenere le parti del draft che il report non ha segnalato

Restituisci SOLO la spiegazione finale corretta.""",
    },

    # ────────────────────────────────────────────────────────────────
    # TEST (pytest generation)
    # ────────────────────────────────────────────────────────────────
    "test": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per ancorare la generazione
dei test a fatti reali rilevati nel progetto.

Le funzioni e classi rilevate nel semantic_context
rappresentano il comportamento osservabile del file.

Usale per determinare:
- cosa testare
- quali edge case sono rilevanti
- quali funzioni sono pubbliche o critiche
- quali branch logici richiedono copertura dedicata

{rendered_context}

# CODICE DA TESTARE

```{language}
{raw_input}
```

# GENERA ORA I TEST PYTEST

Applica rigorosamente le regole definite nelle skill sopra.

VINCOLI ASSOLUTI:
- NON inventare comportamento non presente nel codice
- NON correggere bug del codice originale
- se trovi un bug, preserva il comportamento osservato
  e documentalo con commento "# BUG:"
- genera test ancorati al comportamento osservabile
- privilegia test significativi rispetto a test ridondanti

# VINCOLI DI OUTPUT

REGOLE OBBLIGATORIE:
- restituisci SOLO codice pytest valido
- non usare markdown fences
- non aggiungere spiegazioni
- non aggiungere prefazioni
- non aggiungere testo fuori dal codice
- il risultato deve essere pronto per essere salvato
  come file test_<module>.py ed eseguito direttamente

Il file finale deve contenere:
- import validi
- fixture necessarie
- test pytest validi
- struttura Arrange-Act-Assert
- naming descrittivo dei test""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE ORIGINALE

```{language}
{raw_input}
```

# TEST PYTEST DA VALIDARE

```{language}
{draft}
```

# VALIDAZIONE

Sei il reviewer finale della test suite.

Il tuo default e' BLOCCARE.

Cerca attivamente:
- test non deterministici
- copertura insufficiente
- edge case mancanti
- assert deboli o banali
- dipendenze tra test
- uso scorretto di fixture
- mocking inutile
- violazioni delle skill
- dettagli implementativi testati al posto
  del comportamento osservabile

Verifica in particolare:
- sintassi pytest valida
- pytest --collect-only passerebbe?
- ogni funzione pubblica ha almeno un happy path?
- gli edge case richiesti sono presenti?
- i test sono indipendenti?
- il protocollo BUG e' rispettato?
- naming e struttura AAA sono corretti?
- i test riflettono il comportamento reale del codice?

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# CODICE ORIGINALE

```{language}
{raw_input}
```

# TEST DA CORREGGERE

```{language}
{draft}
```

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi la test suite usando il validation report.

REGOLE OBBLIGATORIE:
- mantieni i test validi gia presenti
- correggi SOLO i problemi segnalati
- preserva il comportamento osservabile del codice originale
- NON correggere silenziosamente bug del codice originale
- se esiste un bug, documentalo con commento "# BUG:"
- mantieni naming descrittivo e struttura AAA
- restituisci SOLO codice pytest valido
- non usare markdown fences nell'output finale
- non aggiungere spiegazioni
- non aggiungere testo fuori dal codice
- il risultato deve essere sintatticamente valido
- mantieni le parti del draft che il report non ha segnalato""",
    },

    # ────────────────────────────────────────────────────────────────
    # DIFF (git diff review)
    # ────────────────────────────────────────────────────────────────
    "diff": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica della codebase. Usale per inquadrare il diff
nel contesto reale del progetto.

{rendered_context}

# FILE IMPATTATI

I file seguenti sono quelli toccati dal diff o che dipendono
da simboli modificati. Il contenuto e' la versione CORRENTE
del file (post-modifica), non quella precedente.

{impacted_files_block}

# DIFF DA ANALIZZARE

Range git: {range_spec}

```diff
{raw_input}
```

# ESEGUI ORA LA REVIEW DEL DIFF

Applica rigorosamente le regole definite nella skill diff_review.

VINCOLI ASSOLUTI:
- Focus sui CAMBIAMENTI, non sui file completi
- Non commentare codice non modificato dal diff
- Non commentare codice cancellato come fosse problematico
  (la cancellazione e' una scelta intenzionale del committente)
- Identifica breaking change solo su simboli che hai motivo
  di considerare pubblici (vedi sezione 3 della skill)
- Severity calibrata: usa critical solo per impatto immediato
- Sezioni "## Rischi" e "## Suggerimenti" SOLO se hanno
  contenuto reale (non sezioni vuote con "Nessun problema rilevato")

Produci l'output nel formato esatto definito dalla skill diff_review:
- "## Sommario" sempre
- "## Modifiche rilevanti" sempre
- "## Rischi" se ci sono rischi
- "## Suggerimenti" se ci sono suggerimenti

Non aggiungere prefazioni.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# DIFF ORIGINALE

```diff
{raw_input}
```

# REVIEW DEL DIFF DA VALIDARE

{draft}

# VALIDAZIONE

Sei il reviewer finale della review del diff.

Il tuo default e' BLOCCARE. Cerca attivamente motivi
per non approvare.

Verifica in particolare:
- FOCUS SUL DIFF: la review parla dei cambiamenti del diff,
  non del codice non modificato?
- CONCRETEZZA: ogni rischio cita file e righe specifiche?
  Ogni suggerimento e' applicabile al diff stesso?
- CALIBRAZIONE SEVERITY: i severity sono giustificati dall'impatto
  reale, non gonfiati? Non c'e' un critical per un piccolo refactor?
- ANCORAGGIO "PUBBLICO": i breaking change citano il dato del
  context che giustifica la qualifica di "pubblico"?
- SEZIONI CONDIZIONALI: "## Rischi" e "## Suggerimenti" sono
  presenti SOLO se hanno contenuto reale? Non vuote con disclaimer?
- ASSENZA DI FILLER: niente "Nessun rischio rilevato",
  "Codice ben scritto", "Continuate cosi'"?
- TRATTAMENTO DEL CODICE CANCELLATO: non e' stato commentato
  come problematico, eccetto per breaking change documentati?

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# DIFF ORIGINALE

```diff
{raw_input}
```

# REVIEW DA CORREGGERE

{draft}

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi la review del diff usando il validation report.

REGOLE OBBLIGATORIE:
- mantieni il FOCUS SUL DIFF: niente commenti sul codice non modificato
- correggi SOLO i problemi segnalati dal validation report
- mantieni il formato richiesto dalla skill diff_review:
  - "## Sommario" sempre
  - "## Modifiche rilevanti" sempre
  - "## Rischi" se ci sono rischi reali
  - "## Suggerimenti" se ci sono suggerimenti azionabili
- calibra correttamente le severity (no inflation)
- mantieni le parti del draft che il report non ha segnalato
- non aggiungere prefazioni
- non aggiungere spiegazioni meta su cosa hai corretto

Restituisci SOLO la review finale corretta.""",
    },

    # ────────────────────────────────────────────────────────────────
    # REPO (repository overview)
    # ────────────────────────────────────────────────────────────────
    "repo": {
        "draft": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

Le seguenti informazioni provengono da un'analisi statica
deterministica dell'intero repository. Sono i dati aggregati
a livello di progetto: dimensione, salute architetturale,
rischi, hotspot di complessita.

Ogni affermazione del tuo overview deve essere riconducibile
a uno di questi dati. Non inventare pattern architetturali,
non aggiungere giudizi morali sul codice, non riassumere file
singoli.

{rendered_context}

# REPOSITORY ANALIZZATO

Path: {repo_path}

# ESEGUI ORA L'OVERVIEW

Applica rigorosamente le regole definite nella skill repository_overview.

VINCOLI ASSOLUTI:
- ANCORAGGIO AI DATI: ogni affermazione di fatto deve poter essere
  ricondotta a un campo specifico del context aggregato sopra
- NO INVENZIONE DI PATTERN: non affermare che il progetto usa MVC,
  Clean Architecture, microservizi o altri pattern architetturali
  se non sono dimostrabili dai nomi delle directory o dai dati
- NO GIUDIZI MORALI: niente "ben scritto", "scarsa qualita",
  "scelta discutibile"
- NO FILLER: niente "Continuate il buon lavoro", "Codice promettente"
- NO RIASSUNTO DEL CODICE: l'overview e' sopra il codice, non
  descrive cosa fanno classi o funzioni singole

Produci l'output nel formato esatto definito dalla skill
repository_overview:
- "## Panoramica" sempre (max 200 parole)
- "## Architettura" sempre (max 250 parole)
- "## Salute del codice" sempre (max 350 parole)
- "## Rischi architetturali" SOLO se ci sono rischi (max 300 parole)
- "## Raccomandazioni" SOLO se ci sono raccomandazioni concrete
  (max 250 parole, massimo 5 raccomandazioni)

Non aggiungere prefazioni.""",
        "self_check": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# REPOSITORY ANALIZZATO

Path: {repo_path}

# OVERVIEW DA VALIDARE

{draft}

# VALIDAZIONE

Sei il reviewer finale dell'overview del repository.

Il tuo default e' BLOCCARE. Cerca attivamente motivi
per non approvare.

Verifica in particolare:
- ANCORAGGIO AI DATI: ogni affermazione di fatto e' riconducibile
  a un campo del context aggregato? Affermazioni come "il progetto
  e' ben strutturato" senza supporto da dati specifici sono violazioni
- INVENZIONE DI PATTERN: l'overview afferma pattern architetturali
  (MVC, Clean Architecture, microservizi, CQRS, hexagonal) senza
  prova esplicita nei dati o nei nomi delle directory? Se si',
  severity critical.
- GIUDIZI MORALI: ci sono frasi tipo "ben scritto", "scarsa qualita",
  "scelta discutibile"? Se si', severity high.
- SEZIONI CONDIZIONALI: "## Rischi architetturali" e
  "## Raccomandazioni" sono presenti SOLO se hanno contenuto reale?
  Non vuote con disclaimer?
- DENSITA: l'overview e' almeno 400 parole? Non c'e' filler?
- CONCRETEZZA: le raccomandazioni sono azionabili? Citano i dati
  che le motivano?
- TONO: e' tecnico ma accessibile? I termini tecnici introdotti
  sono spiegati la prima volta?
- RIASSUNTO DEL CODICE: l'overview descrive cosa fanno classi o
  funzioni singole invece di restare a livello di progetto?

{validation_schema}""",
        "correct": """{skills_block}

# CONTESTO STRUTTURALE DEL PROGETTO

{rendered_context}

# REPOSITORY ANALIZZATO

Path: {repo_path}

# OVERVIEW DA CORREGGERE

{draft}

# VALIDATION REPORT

{report_json}

# CORREZIONE

Correggi l'overview usando il validation report.

REGOLE OBBLIGATORIE:
- mantieni l'ANCORAGGIO AI DATI: ogni affermazione deve essere
  riconducibile al context
- rimuovi pattern architetturali inventati non supportati dai dati
- rimuovi giudizi morali e filler
- mantieni il formato richiesto dalla skill repository_overview:
  - "## Panoramica" sempre
  - "## Architettura" sempre
  - "## Salute del codice" sempre
  - "## Rischi architetturali" SOLO se ci sono rischi reali
  - "## Raccomandazioni" SOLO se ci sono raccomandazioni concrete
- mantieni le parti del draft che il report non ha segnalato
- non aggiungere prefazioni
- non aggiungere spiegazioni meta su cosa hai corretto

Restituisci SOLO l'overview finale corretto.""",
    },
}