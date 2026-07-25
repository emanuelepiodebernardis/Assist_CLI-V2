# Assist CLI — Roadmap v0.3.0

**Versione target**: 0.3.0
**Versione di partenza**: 0.2.0 (rilasciata 17 maggio 2026, tag `v0.2.0`)
**Stima durata**: 6–9 settimane di calendario
**Tema centrale**: trasformare le skill v2.5 da documentali a runtime tramite un sistema configurazionale (1 agente generico + N skill)

---

## 1. Tema centrale

Le skill v2.5 introdotte in v0.2.0 dichiarano nel loro frontmatter molte cose — `max_output_words`, `self_check_persona`, `conflict_resolution`, `inject_position` — ma a runtime queste dichiarazioni sono **parzialmente ignorate**. Sono leggibili dall'umano (documentano la skill) ma non sono lette dal codice.

Allo stesso modo, l'architettura ha 7 sottoclassi di `BaseAgent` (`ReviewerAgent`, `GeneratorAgent`, `RefactorAgent`, `ExplainerAgent`, `TestGeneratorAgent`, `DiffReviewerAgent`, `RepoAgent`) che differiscono in modo poco profondo l'una dall'altra. Il `PromptBuilder` ha 24 metodi paralleli (`build_review_prompt`, `build_generate_prompt`, ecc.) che fanno operazioni strutturalmente identiche su dati diversi.

Il tema della v0.3.0 è **chiudere questo divario architetturale**:

- Una sola classe `Agent` generica, configurata a runtime dal frontmatter della skill che esegue
- Un `PromptBuilder` dichiarativo: template di prompt definito nella skill, variabili sostituite a runtime
- La distinzione esplicita tra **Reference context** (regole stabili dalle skill) e **Working context** (dati run-specific dall'analisi statica e dal file) — pattern preso direttamente dal paper MWP (Van Clief & McDermott, arXiv 2603.16021)
- Un `TaskTarget` tipizzato e discriminato che sostituisce il `TaskInput` "trash bag" con 3 campi opzionali

Risultato atteso: **aggiungere una skill nuova diventa "scrivere un SKILL.md"**, non "scrivere un Agent + aggiornare orchestrator + aggiungere comando in commands.py + registrare in registry.yaml + aggiornare PromptBuilder con un nuovo metodo".

In parallelo, la v0.3.0 affronta i **TECH_DEBT critici** che impediscono l'uso del sistema fuori dal cwd dello sviluppatore originale (encoding fragilità, console su pipe Windows, path resolution).

Infine, come bonus a basso costo, la v0.3.0 introduce **base URL configurabile** per il client LLM, permettendo l'uso di Ollama o altri provider Anthropic-compatible senza un client separato. Questo è anche uno stress test naturale del refactor configurazionale.

---

## 2. Stato di partenza (v0.2.0)

Al momento del rilascio v0.2.0 (commit `53b46f1`, tag `v0.2.0`):

**Funzionalità**:
- 7 comandi end-to-end: `review`, `generate`, `refactor`, `explain`, `test`, `diff`, `repo`
- 8 skill in standard v2.5 Hybrid Canonical: `project_rules`, `code_review`, `refactor`, `python_generation`, `documentation`, `diff_review`, `pytest_generation`, `repository_overview`
- 68 test verdi in ~5 secondi (6 integration + 62 unit)
- Mock LLM per test deterministici

**Smoke test reali completati** (con LLM Anthropic):
- `code_review` su `verifier.py`: quality 0.91
- `pytest_generation` su `file_reader.py`: quality 0.91
- `refactor` su `git_diff_extractor.py`: quality 0.95
- `repo` su `.`: quality 0.88
- `diff` su commit `92e143f`: quality 0.92

**TECH_DEBT inventoriato**: 13 open items, 0 critical, 2 high, 7 medium, 4 low. Documentato in `TECH_DEBT.md`.

**Architettura attuale**:
- `assist/agents/` contiene 7 sottoclassi di `BaseAgent`
- `assist/core/prompt_builder.py` contiene 24 metodi `build_*_prompt`
- `assist/core/orchestrator.py` con branching a 3 vie su `TaskInput.file_path | git_range | repo_path`
- 8 analyzer in `assist/core/` (project_scanner, project_graph, architecture, code_quality, ecc.)
- `assist/skills/` contiene 8 file SKILL.md v2.5
- `config/registry.yaml` mappa comando → agent + skill
- `assist/llm/anthropic_client.py` con `max_tokens=8000` hardcoded

**Cosa è dichiarato nelle skill ma ignorato a runtime**:
- `max_output_words`: parzialmente usato (solo come hint nel prompt)
- `self_check_persona`: definito ma non sempre applicato
- `inject_position`: ignorato
- `conflict_resolution`: definito a parole, non implementato come logica
- `quality_rubric`: deterministico per `code_review`, ma negli altri è ignorato dal verifier

---

## 3. Epic 1 — Single Agent & Skill-Driven Execution

**Obiettivo**: trasformare le 7 sottoclassi `Agent` in una sola classe generica, configurata a runtime dalla skill.

### 3.1. Refactor di `BaseAgent` → `Agent`

**Prima**:
```python
class ReviewerAgent(BaseAgent):
    def generate_draft(self, task_input): ...
    def self_check(self, draft): ...
    def correct(self, draft, report): ...

class GeneratorAgent(BaseAgent):
    def generate_draft(self, task_input): ...
    # ... e così via per 7 classi
```

**Dopo**:
```python
class Agent:
    def __init__(self, skill: Skill, llm_client: LLMClient):
        self.skill = skill
        self.llm = llm_client
        # Configurazione letta dal frontmatter:
        self.max_corrections = skill.frontmatter.max_corrections
        self.output_format = skill.frontmatter.output_format
        self.self_check_persona = skill.frontmatter.self_check_persona

    def execute(self, task_target: TaskTarget) -> AgentOutput:
        # Loop generico draft → self_check → correct
```

**Criteri di completamento**:
- ✓ Le 7 sottoclassi sono cancellate
- ✓ Una sola classe `Agent` esiste in `assist/agents/agent.py`
- ✓ `tests/unit/agents/` consolidato in `test_agent.py` con casi parametrici sulle 8 skill
- ✓ Tutti i test esistenti che usavano `ReviewerAgent` ecc. sono aggiornati
- ✓ Test suite resta verde (≥68 test)

### 3.2. PromptBuilder dichiarativo

**Prima**: 24 metodi `build_<task>_prompt` in `assist/core/prompt_builder.py`, ognuno con logica leggermente diversa.

**Dopo**: un solo metodo `build_prompt(skill, task_target, context)` che:
1. Carica il template di prompt dalla skill (sezione `## Prompt Template` del SKILL.md)
2. Sostituisce le variabili (`{file_content}`, `{static_analysis}`, `{diff_text}`, ecc.) con i dati di runtime
3. Inserisce il contenuto della skill nella sezione `[REFERENCE]` (vedi Epic 2)

**Criteri di completamento**:
- ✓ `PromptBuilder` ha al massimo 5 metodi pubblici (era 24)
- ✓ Ogni SKILL.md ha una sezione `## Prompt Template` con placeholder
- ✓ Sostituzione delle variabili è gestita da una utility comune
- ✓ Test in `test_prompt_builder.py` aggiornati
- ✓ Smoke test reali su tutte e 7 task con quality score ≥ baseline v0.2.0

### 3.3. Migrazione skill v2.5 → v3.0

**Frontmatter v3.0 aggiunge**:
```yaml
version: 3.0
task_type: prose | code | json
output_format:
  type: markdown | python | json
  sections:  # solo per prose
    - name: "## Sommario"
      required: true
    - name: "## Problemi critici"
      required: false
inputs:
  required:
    - file_content
    - static_analysis_facts
  optional:
    - cross_file_context
process:
  prompt_template_path: "templates/code_review.txt"
  self_check_template_path: "templates/code_review_check.txt"
  max_corrections: 1
```

**Criteri di completamento**:
- ✓ Tutte le 8 skill migrate a v3.0
- ✓ `SkillResolver` parsea il nuovo frontmatter
- ✓ Validatore che verifica le skill abbiano tutti i campi obbligatori
- ✓ `docs/SKILL_FORMAT.md` aggiornato con v3.0
- ✓ Test in `test_skill_resolver.py` aggiornati

**Stima Epic 1**: 2–3 settimane.

---

## 4. Epic 2 — Reference / Working Context Separation

**Obiettivo**: separare esplicitamente nel prompt il contesto "stabile" (skill, regole) dal contesto "run-specific" (file, analisi statica), seguendo il pattern Layer 3 vs Layer 4 di MWP.

### 4.1. Struttura del prompt rivista

**Prima** (mescolato):
```
You are a Python code reviewer.
Apply these rules: <skill content>
Review this file: <file content>
Static analysis: <data>
```

**Dopo** (separato):
```
[SYSTEM]
You are an Agent executing the "code_review" skill.

[REFERENCE / Constraints - stable across runs]
== Skill: project_rules ==
<content>
== Skill: code_review ==
<content>

[WORKING / Materials - this run]
== File: assist/core/verifier.py ==
<content>
== Static Analysis ==
- Dead functions: [...]
- God classes: [...]
- Cycles: [...]

[INSTRUCTION]
Apply REFERENCE constraints to the WORKING materials.
Produce output in the format defined by code_review skill.
```

### 4.2. Validazione degli input dichiarati

Ogni skill v3.0 dichiara nel frontmatter quali input richiede. Il PromptBuilder verifica che tutti gli input dichiarati come `required` siano disponibili prima di costruire il prompt. Se mancano, errore chiaro all'utente.

**Criteri di completamento**:
- ✓ PromptBuilder produce prompt con sezioni `[REFERENCE]` e `[WORKING]` esplicite
- ✓ Validatore degli input rifiuta esecuzioni con input mancanti, con messaggio chiaro
- ✓ Smoke test reali: confronto tra "vecchio prompt" e "nuovo prompt" su almeno 3 task, con verifica che quality score non scenda
- ✓ Ideale: quality score migliora di ≥0.02 su almeno 2 task grazie alla separazione

**Stima Epic 2**: 1–2 settimane.

---

## 5. Epic 3 — TaskTarget Discriminato

**Obiettivo**: sostituire `TaskInput` (3 campi opzionali) con `TaskTarget` (varianti tipizzate).

### 5.1. Refactor del modello

**Prima**:
```python
class TaskInput(BaseModel):
    file_path: Optional[Path] = None
    git_range: Optional[str] = None
    repo_path: Optional[Path] = None
    task: str
```

**Dopo**:
```python
class TaskTarget(BaseModel):  # Union discriminato
    pass

class FileTarget(TaskTarget):
    type: Literal["file"]
    file_path: Path

class GitRangeTarget(TaskTarget):
    type: Literal["git_range"]
    range: str

class RepoTarget(TaskTarget):
    type: Literal["repo"]
    repo_path: Path

class TaskRequest(BaseModel):
    target: TaskTarget
    task: str
```

### 5.2. Orchestrator semplificato

L'orchestrator usa pattern matching (Python 3.10+) sul tipo di `TaskTarget`:

```python
match task_request.target:
    case FileTarget(file_path=p):
        # gestisce file
    case GitRangeTarget(range=r):
        # gestisce diff
    case RepoTarget(repo_path=p):
        # gestisce repo
```

**Criteri di completamento**:
- ✓ `TaskInput` cancellato, sostituito da `TaskTarget` discriminato
- ✓ Orchestrator usa pattern matching, niente più `if/elif` su 3 campi opzionali
- ✓ Errori di validazione più chiari (es. "Cannot pass file_path with task=diff")
- ✓ Test in `test_models.py` aggiornati
- ✓ TECH_DEBT 6.3 chiuso

**Stima Epic 3**: 3–5 giorni.

---

## 6. Epic 4 — TECH_DEBT critici

**Obiettivo**: chiudere i TECH_DEBT che bloccano usability esterna o impattano direttamente il refactor.

### 6.1. max_tokens parametrizzabile (TECH_DEBT 1.1)

**Problema attuale**: `AnthropicClient.__init__` ha `max_tokens=8000` hardcoded. Per file molto grandi è insufficiente; per file piccoli è spreco.

**Soluzione**:
- `max_tokens` configurabile via:
  1. Frontmatter della skill (`output_format.max_tokens`)
  2. Variabile env `ASSIST_MAX_TOKENS`
  3. Flag CLI `--max-tokens`
- Default ragionato per output format:
  - `prose`: 4000
  - `code`: 8000
  - `json`: 2000

**Criteri**:
- ✓ Niente più valori hardcoded in `AnthropicClient`
- ✓ Configurazione documentata nel README
- ✓ Test verificano la priorità (CLI > env > skill > default)

### 6.2. FileReader robusto su encoding (TECH_DEBT 2.1, severity high)

**Problema attuale**: `FileReader` assume UTF-8. Files in latin-1, cp1252, o con BOM crashano.

**Soluzione**:
- Detection automatica encoding tramite `chardet` o `charset-normalizer`
- Fallback strategy: UTF-8 → UTF-8 with BOM → cp1252 → latin-1
- Logging chiaro quando l'encoding non è UTF-8
- Errori non bloccanti: file con caratteri irrecuperabili → skip + warning, non crash

**Criteri**:
- ✓ Test su file di esempio in 4+ encoding diversi
- ✓ Nessun crash su qualunque file di testo nel filesystem
- ✓ Performance: detection encoding < 50ms per file < 1MB

### 6.3. Rich Console su pipe Windows (TECH_DEBT 3.1, severity high)

**Problema attuale**: `assist review file.py > out.md` su Windows produce caratteri Unicode bizantini perché Rich Console non rileva il pipe e usa il colore.

**Soluzione**:
- Detection automatica del TTY: `sys.stdout.isatty()`
- Quando non è TTY: forzare encoding UTF-8 e disabilitare colori/box characters
- Test in CI su Windows runner

**Criteri**:
- ✓ Pipe su Windows produce output puro markdown leggibile
- ✓ TTY su Windows mantiene rendering Rich completo
- ✓ Equivalente su macOS e Linux mantenuto

### 6.4. SkillResolver path-independent (TECH_DEBT 4.1)

**Problema attuale**: `SkillResolver` cerca le skill in `./assist/skills/`, che funziona solo se cwd è la root del repo. Da sottocartelle, fallisce.

**Soluzione**:
- Usare `importlib.resources` o `__file__`-based path resolution
- Le skill sono caricate dal package, non dal cwd
- Funziona dovunque l'utente sia (anche fuori dal repo, dopo `pip install -e .`)

**Criteri**:
- ✓ `assist review file.py` funziona da `assist/core/` o da `/tmp/`
- ✓ Test in `test_skill_resolver.py` verificano path resolution da 3 cwd diversi
- ✓ TECH_DEBT 4.1 chiuso

**Stima Epic 4**: 1–2 settimane.

---

## 7. Epic 5 — Base URL configurabile (opzionale, low cost)

**Obiettivo**: permettere uso di Ollama o altri provider Anthropic-compatible senza un client separato.

### 7.1. Configurabilità del base URL

**Cosa cambia**:
```python
class AnthropicClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None, ...):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url or "https://api.anthropic.com",
        )
```

**Sorgenti configurazione** (priorità decrescente):
1. Argomento esplicito `--base-url`
2. Variabile env `ASSIST_ANTHROPIC_BASE_URL`
3. Default Anthropic

### 7.2. Documentazione "Using with Ollama"

Una sezione nel README:
```markdown
## Using Assist CLI with Ollama (experimental)

You can use Assist CLI with Ollama for privacy or cost reasons.

1. Install Ollama 0.14.0+
2. Pull a model: `ollama pull qwen3-coder:30b`
3. Set environment:
   export ASSIST_ANTHROPIC_BASE_URL=http://localhost:11434
   export ANTHROPIC_API_KEY=ollama
4. Run normally: `assist review file.py`

Quality with local models is typically 10-25% lower than Claude
on qualitative tasks (review, refactor). Use Anthropic for best results.
```

### 7.3. Smoke test con Ollama

Non richiesti per il merge della v0.3.0, ma fortemente raccomandati come **stress test del refactor configurazionale**:
- 1 smoke test `generate` con Qwen3-Coder (output: codice Python)
- 1 smoke test `review` con Qwen3-Coder (output: prose markdown)

Se il refactor è ben fatto, questi devono funzionare meccanicamente (quality score può essere più basso, ma struttura dell'output corretta).

**Criteri di completamento**:
- ✓ `AnthropicClient` accetta `base_url` configurabile
- ✓ Configurazione via CLI + env documentata
- ✓ README aggiornato con sezione Ollama
- ✓ Almeno 1 smoke test con modello non-Anthropic eseguito e documentato

**Stima Epic 5**: 2–3 giorni.

---

## 8. Cosa NON è incluso nella v0.3.0

Esplicitamente fuori dallo scope per evitare scope creep:

- **Skill discovery dinamica** (drop di SKILL.md → comando disponibile auto) → v0.4.0
- **Multi-LLM provider** completo (OpenAI, Vertex, Bedrock) → v0.4.0
- **Workflow / skill composition** (orchestrazione di più skill in sequenza) → v0.4.0
- **Caching dei risultati** (analyzer cache + LLM cache) → v0.4.0
- **TECH_DEBT non critici** (detector falsi positivi, PromptBuilder god class, ecc.) → v0.4.0
- **GIF asciinema** → v1.0.0
- **PyPI distribution** → v1.0.0
- **Skill marketplace / registry** → v1.0.0
- **VSCode extension / MCP server** → v1.0.0+

---

## 9. Input esterni utilizzati per la pianificazione

Le decisioni architetturali della v0.3.0 sono informate da 5 fonti esterne lette in fase di planning:

### 9.1. Paper MWP — arXiv 2603.16021 (Van Clief & McDermott, 2026)
"Interpretable Context Methodology: Folder Structure as Agent Architecture"

**Pattern adottato**:
- **Layer 3 vs Layer 4 separation** (reference material stabile vs working artifacts per-run) → Epic 2
- **Stage contracts con Inputs/Process/Outputs espliciti** → Epic 1.3 (frontmatter v3.0)

### 9.2. ICM repository (RinDig)
Implementazione pratica del paper MWP, con 15 convenzioni operative.

**Pattern adottato**:
- **Canonical sources** (ogni info ha una casa) → Epic 1.3
- **Docs over outputs** (agenti imparano dalle skill, non da output precedenti) → già implicito in Assist CLI

### 9.3. antigravity-awesome-skills (sickn33)
22.9k stars, 1239+ skill in universal SKILL.md format.

**Pattern adottato**:
- **SKILL.md come universal interface** → conferma direzione delle skill v2.5/v3.0
- **Validatore della skill (skill-anatomy, quality-bar)** → Epic 1.3

### 9.4. Google Workspace CLI — `gws`
26k stars, Rust, dinamicamente costruito da Discovery Service.

**Pattern adottato**:
- **Base URL configurabile per provider alternativi** → Epic 5
- **Exit codes strutturati** (rimandato a v0.4.0)
- **Dynamic skill discovery** (rimandato a v0.4.0)

### 9.5. VoltAgent awesome-agent-skills
21.6k stars, 1100+ skill curate da team ufficiali.

**Pattern adottato**:
- **Skill come knowledge package** (non funzione) → Epic 1.3
- **One skill per concern** (separazione di responsabilità nelle skill) → conferma direzione

---

## 10. Metriche di completamento

La v0.3.0 è considerata completa quando **tutti** i seguenti criteri sono verificati:

### Funzionalità
- ✓ Una sola classe `Agent`, le 7 sottoclassi cancellate
- ✓ `PromptBuilder` con ≤5 metodi pubblici (era 24)
- ✓ 8 skill migrate a frontmatter v3.0
- ✓ Prompt con sezioni `[REFERENCE]` e `[WORKING]` esplicite
- ✓ `TaskTarget` discriminato sostituisce `TaskInput`
- ✓ `AnthropicClient` con `base_url` configurabile

### TECH_DEBT chiusi
- ✓ 1.1 (max_tokens hardcoded)
- ✓ 2.1 (FileReader fragile su encoding) — severity high
- ✓ 3.1 (Rich Console su pipe Windows) — severity high
- ✓ 4.1 (SkillResolver path-dependent)
- ✓ 6.3 (TaskInput trash bag)

### Test
- ✓ Test suite ≥75 test, tutti verdi
- ✓ Tempo esecuzione test < 10 secondi
- ✓ Coverage ≥80% (target, non bloccante)
- ✓ Test consolidati per agent (un test parametrico sulle skill, non N test per N classi)

### Smoke test reali (con LLM Anthropic)
Tutti i 7 task eseguiti con quality score ≥ baseline v0.2.0:
- `review` ≥ 0.91
- `generate` ≥ 0.80 (smoke v0.2.0 non disponibile, baseline da definire al primo run)
- `refactor` ≥ 0.95
- `explain` ≥ 0.85 (smoke v0.1.0)
- `test` ≥ 0.91
- `diff` ≥ 0.92
- `repo` ≥ 0.88

Se uno qualunque scende sotto baseline, l'Epic responsabile è incompleto.

### Smoke test bonus (con Ollama, non bloccanti)
- ✓ `generate` con Qwen3-Coder produce codice Python valido (quality ≥ 0.70 accettabile)
- ✓ `review` con Qwen3-Coder produce markdown con sezioni corrette (quality ≥ 0.65 accettabile)

### Documentazione
- ✓ `README.md` aggiornato per v0.3.0 (sostituisce sezioni v0.2.0)
- ✓ `docs/SKILL_FORMAT.md` aggiornato a v3.0
- ✓ `TECH_DEBT.md` con item chiusi spostati a "Resolved" e nuovi item emersi durante v0.3.0 documentati
- ✓ Nuovo: `docs/PROMPT_ARCHITECTURE.md` che documenta Reference vs Working layer
- ✓ CHANGELOG breve in fondo al README o file separato

### Release
- ✓ Tag `v0.3.0` su commit del main pubblico
- ✓ GitHub Release con note di rilascio
- ✓ Branch `main` allineato a `origin/main`

---

## 11. Sequenza raccomandata di esecuzione

L'ordine non è obbligatorio ma minimizza rework:

1. **Settimana 1–3**: Epic 1 (Single Agent + Skill-Driven Execution)
   - Refactor `BaseAgent` → `Agent`
   - PromptBuilder dichiarativo
   - Migrazione skill v3.0
   - Test consolidamento
2. **Settimana 4–5**: Epic 2 (Reference / Working Context)
   - Si basa su Epic 1 (le skill v3.0 dichiarano gli input)
3. **Settimana 5–6**: Epic 3 (TaskTarget) in parallelo con fine Epic 2
   - Indipendente, può essere fatto da chi ha tempo morto
4. **Settimana 6–8**: Epic 4 (TECH_DEBT critici)
   - 4.1, 4.2, 4.3, 4.4 in qualunque ordine, sono indipendenti
5. **Settimana 8–9**: Epic 5 (Base URL configurabile) + smoke test + finalizzazione
   - L'ultimo perché beneficia di tutto il resto già stabile

**Rischio critico**: Epic 1 può estendersi se la migrazione delle skill è più complessa del previsto. Mitigation: ogni skill migrata è un commit indipendente; se Epic 1 sfora, le altre Epic possono comunque procedere su skill non-migrate (modalità transitoria).

---

## 12. Risultato atteso

Al termine della v0.3.0:

**Per lo sviluppatore (te stesso)**: il codice è radicalmente più semplice. Aggiungere un task nuovo è "scrivere un SKILL.md", non modificare 5 file. Le skill che oggi sono documentazione diventano configurazione attiva.

**Per l'utente** (chiunque usi `assist`): il sistema funziona dovunque (path independence), su file in qualunque encoding, su qualunque OS, anche con pipe. Output qualitativamente coerente o migliore.

**Per il futuro**: il refactor configurazionale rende v0.4.0 (skill discovery, multi-LLM, workflow) **possibile** a costi ragionevoli. Senza v0.3.0, v0.4.0 sarebbe un altro grosso refactor.

**Stato del progetto al termine v0.3.0**: ben più del 50% del cammino verso v1.0.0 è completato. La direzione architetturale è chiara, l'ecosistema delle skill è ben definito, le fondamenta di estensibilità sono in posto.

---

*Documento creato il 17 maggio 2026. Soggetto a revisione durante lo svolgimento della v0.3.0 se emergono insight non previsti dagli smoke test o dal lavoro implementativo.*
