# TECH_DEBT

Inventario del debito tecnico noto in Assist CLI. Ogni item è un problema
identificato durante lo sviluppo che è stato consapevolmente **non risolto
subito** per restare nello scope dell'epic in corso. Va affrontato in una
versione futura.

Gli item sono classificati per:

- **Severity**: `critical` (bloccante in casi specifici), `high` (degrada
  l'esperienza), `medium` (limitazione gestibile), `low` (rifinitura).
- **Area**: dove tocca nel codice.
- **Origine**: in quale sessione di sviluppo è stato identificato.
- **Stato**: `open` (da fare), `resolved` (risolto in una versione
  successiva), `wontfix` (deciso di non risolvere).

Versione documento: aggiornato al **2026-05-16**, post-completamento
dell'epic 3.6 (task `repo`).

---

## Indice

1. [Configurazione e client LLM](#1-configurazione-e-client-llm)
2. [Robustezza filesystem](#2-robustezza-filesystem)
3. [Rendering output](#3-rendering-output)
4. [Path resolution](#4-path-resolution)
5. [Qualità dell'analisi statica](#5-qualità-dellanalisi-statica)
6. [Architettura e coupling](#6-architettura-e-coupling)
7. [Testing](#7-testing)
8. [Scoring e self-check](#8-scoring-e-self-check)
9. [Performance e rate limit](#9-performance-e-rate-limit)
10. [Items risolti durante v0.2.0](#10-items-risolti-durante-v020)

---

## 1. Configurazione e client LLM

### 1.1 `max_tokens` hardcoded nel client Anthropic

**Severity**: medium
**Area**: `assist/llm/anthropic_client.py`, `assist/llm/factory.py`, `assist/core/config.py`
**Origine**: smoke test 3.2 / epic 3.6 (debug `assist refactor` su `git_diff_extractor.py`)
**Stato**: parzialmente risolto

Il parametro `max_tokens` di `AnthropicClient.__init__` era originariamente
hardcoded a `1024`, valore troppo basso per task di refactor su file medi
(150+ righe). Durante l'epic 3.6 il valore è stato portato a `8000` per
sbloccare il task `refactor`, ma resta **hardcoded** nel codice.

Problemi residui:

- Il `Settings` (in `config.py`) non espone un campo `max_tokens` né lo
  legge da `settings.yaml`.
- La `LLMFactory.create` non passa `max_tokens` al client; usa solo il
  default del costruttore.
- Esiste un campo `max_input_tokens: int = 4000` in `Settings`, ma è
  **inutilizzato** (mai letto da alcun componente del progetto).

**Soluzione proposta per v0.3.0**:

1. Aggiungere campo `max_output_tokens: int = Field(default=8000)` a
   `Settings`.
2. Rinominare `max_input_tokens` in `max_input_tokens_per_prompt` (se
   ha un futuro uso) o rimuoverlo (se è codice morto).
3. `LLMFactory.create` legge il campo e lo passa al client:
   ```python
   return AnthropicClient(
       model=settings.model,
       temperature=settings.temperature,
       max_tokens=settings.max_output_tokens,
   )
   ```

**Workaround attuale**: il default 8000 copre il 99% dei casi pratici.
Per task che richiedono output più grande (es. refactor su file > 300
righe), l'utente deve modificare manualmente il default in
`anthropic_client.py`.

---

### 1.2 `max_input_tokens` dichiarato ma mai usato

**Severity**: low
**Area**: `assist/core/config.py`
**Origine**: ispezione codice durante epic 3.6
**Stato**: open

In `config.py`, `Settings` ha:

```python
max_input_tokens: int = Field(default=4000, ge=1)
```

Il campo è validato da Pydantic ma **nessun componente lo legge**.
Probabilmente era progettato per un futuro sistema di context
truncation (taglia il prompt se supera la dimensione), mai
implementato.

**Soluzione proposta**:

- Decidere se è dead code → rimuovere
- Oppure implementare effettivamente il context truncation in v0.3.0

---

## 2. Robustezza filesystem

### 2.1 `FileReader` fragile su file non-UTF-8

**Severity**: high
**Area**: `assist/utils/file_reader.py`, `assist/core/project_scanner.py`
**Origine**: smoke test 3.6 (debug `assist refactor` su file_reader.py)
**Stato**: open

`FileReader.read()` chiama `path.read_text(encoding="utf-8")` senza
gestione di errori di encoding. Su qualsiasi file non-UTF-8
(UTF-16 con BOM, Windows-1252, file binari), lancia `UnicodeDecodeError`
che propaga fino al CLI.

Per task che scansionano l'intero progetto (`repo`, indirettamente
tutti gli altri che popolano il context), un singolo file con encoding
diverso **interrompe tutta la scansione**.

Casi reali osservati:

- Output di PowerShell `>` redirect su Windows produce file in UTF-16 LE
  con BOM
- File `.bak` generati da operazioni miste possono avere encoding
  inconsistenti
- File binari accidentali con estensione `.py` (raro ma possibile)

**Soluzione proposta per v0.3.0**:

Opzione 1 (rigorosa): `FileReader` lancia un errore tipizzato
`FileEncodingError`, `ProjectScanner` lo cattura e logga warning, salta
il file ma continua la scansione.

```python
class FileEncodingError(Exception):
    """Raised when a file cannot be decoded as UTF-8."""

# In FileReader.read:
try:
    return path.read_text(encoding="utf-8")
except UnicodeDecodeError as exc:
    raise FileEncodingError(
        f"File {path} is not UTF-8: {exc}"
    ) from exc
```

Opzione 2 (pragmatica): skip silenzioso se non-UTF-8. Più semplice ma
nasconde problemi reali.

**Mitigazione parziale già implementata**: nel branch `elif task.repo_path`
dell'`Orchestrator` (epic 3.6), c'è già un `try/except` che cattura
`UnicodeDecodeError` durante l'iterazione sui file per il `code_quality`.
Quindi il task `repo` non si rompe su file non-UTF-8, ma quel file
viene escluso dall'analisi senza warning.

**Workaround attuale**: assicurarsi che tutti i file del progetto siano
UTF-8. Su PowerShell, usare `Out-File -Encoding utf8` invece di `>`.

---

## 3. Rendering output

### 3.1 Rich Console + cp1252 su pipe Windows

**Severity**: high
**Area**: `assist/cli/commands.py`, dipendenza `rich`
**Origine**: smoke test 3.6 (tentativo di redirezione `assist refactor | Out-File`)
**Stato**: open

Quando l'output di `assist` viene pipato a file o ad altro comando
(`Out-File`, `>`, `|`) su Windows, Rich Console entra in modalità
"legacy windows render" che tenta di codificare l'output in cp1252
(codepage default di Windows). Caratteri Unicode comuni (`→` U+2192,
`≥`, `"`) causano `UnicodeEncodeError` e crash dell'applicazione.

L'output viene generato correttamente, ma la sua **stampa** fallisce.

**Impatto**:

- Utenti Windows non possono salvare l'output di `assist` con la
  pipeline standard PowerShell
- Limita l'uso in script CI/CD su Windows
- Costringe a workaround manuali con variabili d'ambiente

**Soluzione proposta per v0.3.0**:

In `_handle_output` (in `assist/cli/commands.py`), detectare se stdout
è un terminale. Se non lo è, bypassare Rich Console e fare
`sys.stdout.write(plain_text)` con encoding UTF-8 esplicito:

```python
import sys

def _handle_output(formatted_output, output_format, output_path=None):
    if output_path:
        # ... codice attuale: scrive su file con encoding utf-8
        return

    if not sys.stdout.isatty():
        # Stdout è una pipe o file: scrittura plain text utf-8
        sys.stdout.buffer.write(
            str(formatted_output).encode("utf-8")
        )
        return

    # Stdout è terminale: rendering Rich completo
    if output_format == "terminal":
        console.print(formatted_output)
    else:
        typer.echo(formatted_output)
```

In alternativa, configurare la Console Rich con `force_terminal=False`
e `legacy_windows=False` quando stdout non è TTY.

**Workaround attuale**:

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
assist <comando> | Out-File -FilePath output.md -Encoding utf8
```

Da configurare prima di ogni redirezione.

---

## 4. Path resolution

### 4.1 `SkillResolver` path-dipendente da cwd

**Severity**: medium
**Area**: `assist/core/skill_resolver.py`
**Origine**: epic 2 (sviluppo `assist diff`, debug integration test)
**Stato**: open

`SkillResolver` calcola `skills_path` relativamente alla **cwd del
processo Python** (`Path("assist/skills")` invece di
`Path(__file__).parent.parent / "skills"`). Risultato: il CLI funziona
solo se eseguito dalla directory radice del repository.

Casi che falliscono oggi:

- `cd /tmp && assist review /path/to/file.py` → `SkillResolver` cerca
  le skill in `/tmp/assist/skills/` (inesistente), fallisce
- Installazione globale via `pip install .` e invocazione da qualsiasi
  directory → fallisce per lo stesso motivo
- Integration test con `monkeypatch.chdir(...)` su tmp_path → fallisce
  (causa del bug architettonico scoperto in epic 2)

**Soluzione proposta per v0.3.0+**:

Usare il path del package `assist` come riferimento:

```python
import assist

class SkillResolver:
    DEFAULT_SKILLS_PATH: Path = (
        Path(assist.__file__).parent / "skills"
    )

    def __init__(self, skills_path: Path | None = None):
        self.skills_path = skills_path or self.DEFAULT_SKILLS_PATH
```

In questo modo le skill vengono trovate ovunque viene installato il
package, indipendentemente dalla cwd di esecuzione.

**Workaround attuale**: invocare sempre `assist` dalla root del
repository.

---

## 5. Qualità dell'analisi statica

### 5.1 Dead code detector con falsi positivi

**Severity**: medium
**Area**: `assist/core/dead_code_detector.py`, `assist/core/code_quality_analyzer.py`
**Origine**: smoke test 3.6 (output di `assist repo .`)
**Stato**: open

Il rilevatore di dead code segnala come "potenzialmente inutilizzate"
funzioni che in realtà sono:

- Entry point di test (`test_*` chiamate da pytest tramite discovery)
- Metodi `__init__` di classi (chiamati dall'instantiation)
- Metodi del protocollo `BaseAgent` (`run`, `generate_draft`,
  `self_check`, `correct`) chiamati dinamicamente dall'orchestrator
- Metodi di utility (`complete` dei mock LLM, `__test__ = False` flags)
- Funzioni di fixture pytest (`_patch_analyzers` e simili)

L'analizzatore non distingue tra:

- "Funzione mai chiamata" (= dead code vero)
- "Funzione chiamata dinamicamente" (= falso positivo)
- "Funzione chiamata da framework esterni" (= falso positivo)

**Soluzione proposta**:

Aggiungere una **lista di esclusioni** per pattern noti:

- Funzioni con prefisso `test_`
- Metodi dunder (`__init__`, `__call__`, `__enter__`, ecc.)
- Metodi del protocollo agent (`run`, `generate_draft`, `self_check`, `correct`)
- Funzioni decorate con `@pytest.fixture`, `@click.command`, `@typer.command`
- Classi con attributo `__test__ = False`

Implementazione: nel `DeadCodeDetector`, prima di marcare una funzione
come dead, controllare se matcha uno dei pattern di esclusione.

---

### 5.2 Isolated module detector con falsi positivi

**Severity**: medium
**Area**: `assist/core/architectural_risk_analyzer.py`
**Origine**: smoke test 3.6 (output di `assist repo .`)
**Stato**: open

L'analizzatore di "isolated modules" segnala come "isolati" file che
sono in realtà importati ovunque. Caso documentato: `assist/schemas/models.py`
appare in `risk_context.risks` come `isolated_module` severity medium,
nonostante sia importato da quasi tutti i moduli del progetto
(confermato da `cross_file_context.imports`).

Probabile causa: l'analizzatore non riconosce import del tipo
`from assist.schemas.models import X` come dipendenza da `models.py`.
Forse cerca matches solo su path completo (`assist/schemas/models.py`)
e non su nome modulo (`assist.schemas.models`).

Altri falsi positivi osservati:

- File `__init__.py` di tutti i sotto-pacchetti (segnalati come isolati
  anche se Python li carica automaticamente)
- File standalone non collegati al package principale (es. `test.py`
  alla root del progetto) — questi sono **veri** isolated, ma il detector
  non distingue dai falsi positivi

**Soluzione proposta**:

Rivedere la logica di matching tra import statements e file paths nel
detector. Considerare l'uso di un grafo di import più robusto
(`networkx`?) invece di analisi testuale.

---

## 6. Architettura e coupling

### 6.1 `orchestrator.py` ha fan-out elevato

**Severity**: medium
**Area**: `assist/core/orchestrator.py`
**Origine**: smoke test 3.6 (output di `assist repo .`)
**Stato**: open

`orchestrator.py` ha **26 dipendenze dichiarate** (verificato dallo stesso
sistema durante lo smoke test del task `repo`). È il file con fan-out più
alto dell'intero repository e funge da punto di coordinamento centrale
tra agenti, analizzatori e LLM.

Pattern attuale: tre branch (`if task.git_range`, `elif task.file_path`,
`elif task.repo_path`) ognuno con logica complessa di popolamento context.
Il branch `repo_path` da solo è ~140 righe.

**Implicazioni**:

- Qualsiasi modifica a uno dei 26 moduli dipendenti può richiedere
  aggiornamenti all'orchestratore
- Test dell'orchestrator (`test_orchestrator.py`) ha 12 dipendenze:
  rispecchia il coupling del modulo che testa
- Aggiungere un quarto branch (es. futuro `task.url` per scaricare repo
  da GitHub) richiederebbe duplicare ulteriormente la logica

**Soluzione proposta per v0.3.0+**:

Decomporre `orchestrator.py` in coordinatori specializzati:

```
orchestrator/
  __init__.py            # punto di ingresso principale
  context_builder.py     # costruzione del context per task
  task_dispatcher.py     # routing del task all'agente appropriato
  diff_context.py        # logica specifica per task git_range
  file_context.py        # logica specifica per task file_path
  repo_context.py        # logica specifica per task repo_path
```

Effort stimato: grande (1+ settimana). Va fatto in un'epic dedicata di
v0.3.0, non come scope creep.

---

### 6.2 `PromptBuilder` e `OutputFormatter` classificate come god class

**Severity**: medium
**Area**: `assist/core/prompt_builder.py`, `assist/core/output_formatter.py`
**Origine**: smoke test 3.6 (output di `assist repo .`)
**Stato**: open

Entrambe le classi sono state classificate come "god class" dal
`code_quality_analyzer`, con numerosi `complexity_warnings` sulle
loro funzioni:

- `PromptBuilder` ha 24 metodi statici (`build_review_prompt`,
  `build_review_self_check_prompt`, `build_review_correction_prompt`,
  e analoghi per generate/refactor/explain/test/diff/repo). Ogni task
  ha 3 metodi che condividono struttura ma differiscono nei dettagli.
- `OutputFormatter` ha logica di rendering per 3 tipi di task
  (PURE_CODE, MIXED_CODE, PROSE) con 3 path di formattazione diversi
  (`format_terminal`, `format_markdown`, `format_json`).

**Soluzione proposta per v0.3.0**:

Per `PromptBuilder`:

```
prompt_builder/
  base.py            # helper comuni (_build_skills_block, _build_context_block)
  review_prompts.py  # 3 metodi per review
  generate_prompts.py
  refactor_prompts.py
  explain_prompts.py
  test_prompts.py
  diff_prompts.py
  repo_prompts.py
```

Per `OutputFormatter`: estrarre i renderer per tipo di task in classi
separate (`PureCodeRenderer`, `MixedCodeRenderer`, `ProseRenderer`).

Effort stimato: medio (1 giorno ciascuna). Va fatto durante la v0.3.0
quando il sistema configurazionale richiederà probabilmente un
ripensamento del `PromptBuilder` da metodi statici a sistema
dichiarativo.

---

### 6.3 `TaskInput` come trash bag

**Severity**: low
**Area**: `assist/schemas/models.py`
**Origine**: epic 3.6 (decisione architetturale aggiunta `repo_path`)
**Stato**: open

`TaskInput` ha ora 3 campi opzionali per identificare il target:
`file_path`, `git_range`, `repo_path`. Funziona, ma:

- L'orchestrator deve branchare su 3 condizioni `if/elif/elif`
- Aggiungere un quarto tipo di target richiederebbe modificare TaskInput,
  l'orchestrator, e probabilmente i comandi CLI
- La semantica non è esplicita: dal solo `TaskInput` non si capisce
  immediatamente "questo task è file/diff/repo"

**Soluzione proposta per v0.3.0+ (opzionale)**:

Refactor verso un "target dispatcher" pattern:

```python
class TaskTarget(BaseModel):
    kind: Literal["file", "git_range", "repo"]
    value: str

class TaskInput(BaseModel):
    command: str
    target: TaskTarget
    language: str = "python"
    options: dict = {}
```

Pro: design estensibile (futuro `kind="url"`, `kind="github_pr"`).
Contro: rompe la retro-compatibilità di TaskInput, tutti i 7 task
esistenti e i loro test vanno aggiornati.

**Decisione attuale**: rimandato. Il pattern "trash bag" funziona
finché abbiamo solo 3 tipi di target. Diventa scope creep quando
arriverà il 4° tipo.

---

## 7. Testing

### 7.1 Test unitari degli agenti hanno assertion deboli

**Severity**: low
**Area**: `tests/unit/agents/*.py`
**Origine**: epic 1 (sviluppo `test_test_generator_agent.py`)
**Stato**: parzialmente risolto

Alcuni test unitari degli agenti (ReviewerAgent, GeneratorAgent,
RefactorAgent, ExplainerAgent) verificano principalmente che il mock
LLM ritorni la stringa attesa, anziché verificare la logica del prompt
construction.

Esempio del problema:

```python
def test_correct_returns_fixed_tests():
    agent = build_agent(responses=[
        "import pytest\n\ndef test_add_edge_case(): ..."
    ])
    # ...
    corrected = agent.correct(...)
    assert "test_add_edge_case" in corrected  # tautologia mascherata
```

Il mock LLM è programmato a ritornare una stringa che contiene
`test_add_edge_case`. L'assertion non può fallire a meno che
`agent.correct()` non manipoli la risposta (cosa che non fa).

**Mitigazione parziale già implementata**: i test più recenti
(`test_test_generator_agent.py` parzialmente, `test_diff_reviewer_agent.py`
e `test_repo_agent.py` interamente) verificano anche il **prompt
costruito**:

```python
assert len(agent.llm.prompts) == 1
prompt = agent.llm.prompts[0]
assert "test_add_happy_path" in prompt  # draft nel prompt
assert "Add edge case coverage" in prompt  # action del report
assert "CORREZIONE" in prompt  # marcatore unico
```

Questo verifica logica reale: che il `PromptBuilder.build_*_correction_prompt`
sia chiamato e produca un prompt con il draft + il report + il marcatore
identificativo della funzione.

**Soluzione proposta per v0.3.0**:

Allineare i 4 test agent vecchi (`test_generator_agent.py`,
`test_reviewer_agent.py`, `test_refactor_agent.py`,
`test_explainer_agent.py`) al nuovo pattern aggiungendo assertion sui
prompt costruiti.

Effort: piccolo (~30 min totali, 4 file da modificare con pattern
ripetitivo).

---

## 8. Scoring e self-check

### 8.1 `quality_score = 0.00` con output qualitativamente buono (RISOLTO)

**Severity**: high (era)
**Area**: `assist/skills/pytest_generation/SKILL.md`, agent self_check
**Origine**: smoke test 1.8 / epic 1
**Stato**: **resolved in epic 3.2 (migrazione v2.5)**

**Problema originale**: durante lo smoke test di `assist test verifier.py`
in epic 1, l'output era qualitativamente buono ma il `quality_score`
riportato dal sistema era `0.00` con 3 iterations.

**Diagnosi originale**: il self_check applicava la rubrica della skill
v2.0 `pytest_generation`, ma la rubrica era mal calibrata. Il modello
restituiva JSON con `quality_score: 0.0` perché applicava criteri di
giudizio troppo severi (o non strutturati).

**Risoluzione empirica**: durante l'epic 3.2 (migrazione skill v2.0 →
v2.5 Hybrid Canonical), la skill `pytest_generation` è stata
completamente riscritta con una rubrica deterministica binaria pesata
(4 criteri 0.25 ciascuno). Lo smoke test rifatto post-migrazione su
`file_reader.py` ha prodotto `quality_score = 0.91` in 1 iteration.

**Empiricamente confermato**: la migrazione v2.5 ha risolto il
problema. Lo stesso pattern di score 0 era stato ipotizzato come
"bug trasversale" del BaseAgent, ma in realtà era specifico della
rubrica della skill v2.0.

**Lezione appresa**: il `quality_score = 0` non era un bug del codice
Python ma un effetto della skill mal scritta. La rubrica deterministica
v2.5 (criteri binari 0.0/1.0 pesati) è significativamente più
prevedibile della rubrica narrativa v2.0.

---

### 8.2 Score `quality_score` finale dipende solo dall'ultimo self_check

**Severity**: low
**Area**: `assist/agents/base.py`
**Origine**: ispezione codice durante epic 1
**Stato**: open

Il `BaseAgent.run()` traccia il `quality_score` come quello dell'ultimo
`self_check` valido. Se il loop termina con `is_valid: false` (dopo
aver esaurito `max_corrections`), restituisce comunque il `quality_score`
dell'ultimo self_check (che è basso).

**Implicazione**: non è chiaro dalla CLI se il task ha "converso" con
successo o se ha esaurito le iterations senza convergere. Entrambi i
casi possono produrre output ma con segnali diversi.

**Soluzione proposta per v0.3.0**:

Aggiungere a `FinalOutput` un campo `converged: bool` che indica se
l'ultimo self_check è stato `is_valid: true`. Il quality_score resta
informativo ma `converged` dice se il sistema considera l'output
"definitivo" o "il miglior tentativo possibile".

---

## 9. Performance e rate limit

### 9.1 Rate limit Anthropic API con prompt grandi

**Severity**: medium
**Area**: prompt construction (vari file)
**Origine**: smoke test 1.8 (test su file_reader.py) e 2.8 (diff HEAD~1)
**Stato**: open

L'API Anthropic ha rate limit per minuto (tipicamente 30k tokens/min
per tier base). I prompt costruiti da `assist` includono:

- 2-3 skill (5-9k tokens)
- Context strutturale rendered (5-15k tokens, dipende dalla dimensione
  progetto)
- Codice del file target o diff (1-10k tokens)
- Istruzioni operative (~1k tokens)

Su un singolo task con 2-4 chiamate LLM (draft + self_check ±
correzione + self_check finale), si supera facilmente il limite per
file medio-grandi.

Casi che hanno colpito il rate limit:

- `assist test file_reader.py` (epic 1 smoke test 1.8)
- `assist diff HEAD~1` su commit grandi del progetto Assist CLI stesso
  (epic 2 smoke test 2.8)

**Soluzione proposta per v0.3.0+**:

Mitigazioni in ordine di costo:

1. **Caching del context strutturale**: il context è lo stesso per draft
   e self_check. Serializzarlo una volta e riusarlo riduce ~5-10k tokens
   per ogni chiamata successiva al draft.

2. **Compressione del context**: omettere campi vuoti del PromptContext
   nel rendering. Esempio: se `semantic_context.functions == []`, non
   includere la sezione nel prompt.

3. **Dividere review/refactor multi-file**: se il diff coinvolge > N file,
   eseguire N review separate e aggregare i risultati.

4. **Salire di tier API**: soluzione finanziaria, non tecnica.

**Workaround attuale**: aspettare 1-2 minuti tra task pesanti, oppure
testare su file più piccoli.

---

### 9.2 Task `repo` scansiona tutti i file Python del progetto

**Severity**: low
**Area**: `assist/core/orchestrator.py` (branch `elif task.repo_path`)
**Origine**: epic 3.6 (implementazione task `repo`)
**Stato**: open (accettato come trade-off)

Il branch `repo_path` dell'orchestrator itera su tutti i file Python
del progetto chiamando `FileReader`, `SemanticAnalyzer`, e
`CodeQualityAnalyzer` su ognuno per accumulare gli aggregati di code
quality.

**Costo osservato** (su progetto Assist CLI con ~100 file Python):

- ~30-60 secondi di latenza prima della chiamata LLM
- ~3000-5000 tokens di context aggregato nel prompt

**Impatto**: latenza percepita alta. Su progetti più grandi (es. 500+
file), potrebbe diventare proibitiva.

**Soluzioni possibili per v0.3.0+**:

1. **Parallelizzazione**: scansionare i file in parallelo con
   `concurrent.futures.ThreadPoolExecutor`.

2. **Caching dei report di analisi**: salvare i `CodeQualityReport` per
   file (con hash del contenuto come chiave) e riusarli se il file non
   è cambiato.

3. **Filtraggio top-N**: invece di aggregare tutto, prendere solo i
   top 10 god class, top 20 long method, ecc. Riduce il context senza
   perdere il segnale utile.

**Decisione attuale**: accettato per ora. Il task `repo` è eseguito
raramente (non in workflow giornaliero), quindi 30-60 secondi di
latenza sono tollerabili.

---

## 10. Items risolti durante v0.2.0

Inventario degli item identificati e **risolti** durante lo sviluppo
della v0.2.0. Tenuti qui per memoria storica.

### 10.1 Quality score = 0.00 su `assist test`

Risolto empiricamente dalla migrazione skill v2.0 → v2.5 (epic 3.2).
Vedere item 8.1 sopra.

### 10.2 `max_tokens=1024` blocca `assist refactor` su file medi

Mitigato in epic 3.6: default cambiato a `8000` in
`anthropic_client.py`. Il problema strutturale (non configurabile)
resta open, vedere item 1.1.

### 10.3 Conftest condiviso per integration test

Risolto in epic 3.1: estratta `patch_all_analyzers` fixture in
`tests/integration/conftest.py`. Riduzione ~200 righe di codice
duplicato. 5 integration test esistenti aggiornati al pattern fixture.

### 10.4 Skill format eterogeneo (famiglia A vs B)

Risolto in epic 3.2: scritto `SKILL_FORMAT.md` v2.5 Hybrid Canonical.
Migrate tutte le 7 skill attive del progetto al nuovo standard
(project_rules, code_review, python_generation, refactor, documentation,
diff_review, pytest_generation, repository_overview).

### 10.5 `repository_overview` non aveva un task associato

Risolto in epic 3.6: implementato task `repo` end-to-end (schemi,
agent, prompt builder, orchestrator, CLI, integration test, smoke
test reale).

---

## Stato sintetico v0.2.0

| Severity | Open | Resolved | Wontfix |
|---|---|---|---|
| critical | 0 | 0 | 0 |
| high | 2 | 1 | 0 |
| medium | 7 | 1 | 0 |
| low | 4 | 0 | 0 |
| **Totale** | **13** | **2** | **0** |

**Items open critici nessuno**. La v0.2.0 è in stato di salute
operativa: i 7 task funzionano, i 68 test sono verdi, le 5 raccomandazioni
emerse dallo smoke test del task `repo` (vedere item 5.1, 5.2, 6.1,
6.2, 9.2) sono limitazioni note e tracciate, non bloccanti.

**Priorità per v0.3.0** (ordine suggerito):

1. **Sistema configurazionale** che legge i campi del frontmatter delle
   skill v2.5 (`max_output_words`, `self_check_persona`, `inject_position`)
   e li applica automaticamente. Questo abilita anche la soluzione di
   items 1.1, 6.2.

2. **`FileReader` robustezza** (item 2.1) — sblocca scenari operativi
   reali (scansione progetti con file misti).

3. **Rich Console su pipe Windows** (item 3.1) — sblocca workflow di
   redirezione output, importante per CI/CD.

4. **`SkillResolver` path resolution** (item 4.1) — sblocca installazione
   globale del CLI.

5. **Detectors quality** (items 5.1, 5.2) — migliora la qualità degli
   output del task `repo` riducendo i falsi positivi.

I restanti items sono rifiniture o miglioramenti incrementali da
affrontare quando il tempo lo permette.
