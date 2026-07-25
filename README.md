# Assist CLI

A modular command-line coding assistant for Python that combines deterministic
static analysis with LLM agents under declarative skill constraints.

Each command runs through a verifiable pipeline: code analysis produces
structural facts about your codebase, skills encode quality rules, and
specialized agents produce output that passes a self-validation loop plus a
global verification layer before reaching you.

```
68 tests passing in ~5 seconds. Pipeline validated end-to-end with MockLLM
and through smoke tests on real LLM calls.
```

---

## What it does

Seven commands, one specialized agent per task:

| Command | Agent | Purpose |
| --- | --- | --- |
| `assist review <file>` | ReviewerAgent | Technical review with concrete fixes |
| `assist generate <file>` | GeneratorAgent | Generate Python code from a text specification |
| `assist refactor <file>` | RefactorAgent | Refactor code while preserving observable behavior |
| `assist explain <file>` | ExplainerAgent | Technical explanation anchored to project context |
| `assist test <file>` | TestGeneratorAgent | Generate pytest test suite for a target file |
| `assist diff [range]` | DiffReviewerAgent | Review a git diff (commit, range, or working tree) |
| `assist repo [path]` | RepoAgent | High-level overview of an entire repository |

Every command produces structured output with:

- A **quality score** (0.0–1.0) computed by a deterministic rubric defined
  in the applicable skill
- A **verification table** (syntax, format, coherence, task-aware checks)
- An **iteration count** showing how many self-correction passes were needed

---

## What it is not

To set the right expectations from the start:

- **Not a chat assistant.** No conversation, no memory between invocations.
  Each command is an atomic operation with well-defined input and output.
- **Not a generic LLM wrapper.** Every invocation applies structural
  constraints, declarative skills, and verifiable quality gates.
- **Not a linter.** Static analysis is infrastructure, not output. The final
  result is always produced by an LLM, under constraints.
- **Not an autonomous agent.** Produces text or code for you to review.
  Executing changes remains a human decision.

---

## Installation

Requires Python 3.10+ (tested on 3.13) and an Anthropic API key.

```bash
git clone https://github.com/emanuelepiodebernardis/Assist_CLI.git
cd Assist_CLI
pip install -e .
```

Set the API key:

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Verify the install:

```bash
assist --help
```

---

## Quick start

### Review a file

```bash
assist review path/to/module.py
```

Produces a technical review with `## Sommario`, `## Problemi critici`,
`## Problemi significativi`, `## Suggerimenti`. The review uses
static-analysis facts (dead code, cyclic imports, god classes, complexity
warnings) to ground itself in real findings rather than generic impressions.

### Explain a file

```bash
assist explain path/to/module.py --depth brief
```

Available depth values: `brief`, `verbose`. The explanation covers purpose,
structure, responsibilities, dependencies, and notable critical points —
anchored in the project context.

### Refactor a file

```bash
assist refactor path/to/module.py --target readability
```

Strict behavioral-invariance constraint: the refactor cannot change
observable behavior. If a bug is found in the original, it is preserved and
reported in `## Note`, not silently fixed.

### Generate code

```bash
assist generate output_file.py --prompt "Implement a binary search function for sorted integer lists"
```

Produces pure Python (no markdown fences) ready to be saved.

### Generate tests

```bash
assist test path/to/module.py
```

Produces a pytest test suite for the target file. Tests follow the
Arrange-Act-Assert pattern, use `pytest.raises` for error cases, prefer
fixtures and parametrize when applicable. If the original file contains a
bug, the test preserves the buggy behavior and documents it with a `# BUG:`
comment instead of silently testing the "correct" behavior.

### Review a git diff

```bash
# Last commit
assist diff HEAD

# Last 3 commits
assist diff HEAD~3

# Range between branches
assist diff main..feature

# Only staged changes
assist diff --cached
```

The output focuses exclusively on the changes introduced by the diff, not
on the surrounding code. Identifies breaking changes on public symbols
(verified through cross-file usage analysis), regression risks, and side
effects not declared in the modified signatures.

### Repository overview

```bash
# Current directory
assist repo

# Specific path
assist repo /path/to/project
```

Produces a high-level overview of the entire repository: project size,
architecture (cycles, highly connected files, health score), code health
(god classes, long methods, complexity warnings, dead functions),
architectural risks, and actionable recommendations with effort estimates.

Every claim in the overview is anchored to a specific field of the
aggregated structural context — no invented architectural patterns, no
moral judgments on the code.

### Output formats

All commands accept:

```
--format terminal   # Rich rendering (default)
--format markdown   # Raw markdown for piping or saving
--format json       # Structured output for tooling
--output report.md  # Save to file instead of stdout
```

Note: `refactor` uses `--output` for the output file path; all other
commands use `--output` as well.

---

## Example: real output

Here is an excerpt of what `assist repo .` produced when run on the
project's own codebase (quality score 0.88, 1 iteration):

```
╭─────────────── Repository Overview ───────────────╮
│                                                    │
│ ## Panoramica                                      │
│                                                    │
│ Il repository contiene 103 file Python             │
│ (repository_context.project_size) organizzati nel  │
│ pacchetto principale assist/ con sotto-pacchetti   │
│ agents/, cli/, core/, llm/, schemas/, utils/ e     │
│ skills/. La suite di test è separata in            │
│ tests/unit/ e tests/integration/. Il conteggio     │
│ totale delle dipendenze dichiarate è 202.          │
│                                                    │
│ ## Architettura                                    │
│                                                    │
│ Nessun ciclo di import rilevato. Il file           │
│ orchestrator.py ha 26 dipendenze dichiarate: è il  │
│ file con il fan-out più alto del repository e      │
│ funge da punto di coordinamento centrale.          │
│ Health score: 0.75.                                │
│                                                    │
│ ## Salute del codice                               │
│                                                    │
│ God class identificate: 2 (OutputFormatter,        │
│ PromptBuilder). Una god class è una classe con     │
│ troppe responsabilità concentrate: rende difficile │
│ modificare un comportamento senza rischiare        │
│ regressioni su altri.                              │
│                                                    │
│ ...                                                │
╰────────────────────────────────────────────────────╯
```

The overview identifies real architectural patterns of the project,
anchors every claim to a specific data field (`repository_context.project_size`,
`risk_context`), and produces actionable recommendations with effort
estimates. It is the kind of overview a new team member would want to read
in the first 10 minutes after cloning the repo.

The 5 recommendations the system produced have been collected as items in
[`TECH_DEBT.md`](TECH_DEBT.md). Self-applied diagnostics in action.

---

## How it works

```
CLI command
   ↓
Orchestrator (branches on task type: file / git_range / repo_path)
   ↓
Static analysis layer (8 analyzers)
   ↓
Registry (resolves agent + skills for the task)
   ↓
SkillResolver (loads skills with YAML frontmatter v2.5)
   ↓
Agent
   └─ generate_draft → self_check → correct → self_check → ...
   ↓
GlobalVerifier (syntax, non-empty, placeholders, task-aware)
   ↓
OutputFormatter (terminal | markdown | json)
   ↓
You
```

### Static analysis layer

Eight analyzers run on every invocation, producing typed Pydantic reports:

- **ProjectScanner** — file enumeration with metadata
- **ProjectGraphBuilder** — dependency graph at module level
- **ArchitectureAnalyzer** — cyclic dependency detection
- **RepositoryHealthAnalyzer** — overall health score (0.0–1.0)
- **ArchitecturalRiskAnalyzer** — risk classification (fan-out, depth, coupling)
- **SemanticAnalyzer** — functions, classes, imports, calls per file
- **CrossFileAnalyzer** — inter-file imports and function calls
- **CodeQualityAnalyzer** — complexity warnings, dead functions, long methods, god classes

The results are aggregated into a structural context block injected into
the LLM prompt. For `repo`, the analyzers are applied at the aggregated
project level rather than to a single target file.

### Self-validation loop

Each agent inherits from `BaseAgent` and implements three methods:
`generate_draft`, `self_check`, `correct`. The base loop:

```
draft = generate_draft()
for iteration in 1..max_corrections+1:
    report = self_check(draft)
    if report.is_valid: break
    if iteration == max_corrections+1: break  # final pass: validate, do not correct
    draft = correct(draft, report)
return AgentOutput(quality_score=report.quality_score, ...)
```

Key property: the `quality_score` always reflects the **final** draft, not
an intermediate one. The reported score is honest about what the user
actually receives.

`max_corrections` is differentiated per agent: code-producing agents
(Generator, Refactor, TestGenerator) get 2 correction passes; prose
agents (Reviewer, Explainer, DiffReviewer) get 1; RepoAgent gets 2 given
the complexity of the structured 5-section output.

### Skills (v2.5 Hybrid Canonical)

Eight declarative skills in `assist/skills/`:

- `project_rules` — Base style and quality rules; injected in every task
- `code_review` — Output format and severity calibration for reviews
- `python_generation` — Type hints, docstring style, naming conventions
- `refactor` — Refactoring patterns and behavioral-invariance protocol
- `documentation` — Structure for explanations and docstrings
- `diff_review` — Diff-specific rules: focus on changes, breaking change detection
- `pytest_generation` — pytest patterns, AAA structure, bug protocol
- `repository_overview` — Repository-level synthesis, anti-pattern-invention guards

Every skill has a YAML frontmatter declaring `applies_to`, `priority`,
`max_output_words`, `conflict_resolution`, `inject_position`,
`self_check_persona`. Skills aren't generic suggestions to the model —
they're contracts with explicit conflict-resolution rules and adversarial
self-check personas.

Each skill follows the v2.5 Hybrid Canonical standard documented in
[`docs/SKILL_FORMAT.md`](docs/SKILL_FORMAT.md): 9 canonical sections
(Scope, Posture, Context data, Operational rules, Output format, Examples,
Absolute constraints, Self-check, Rubric), declarative frontmatter with
slug-expanded prose, and a binary quality_score rubric with asymmetric
weights.

### Task-aware verifier

`GlobalVerifier` runs three universal checks (syntax, non-empty,
placeholders) but adapts to the task type. For `refactor`, output is
markdown with an embedded code block — the verifier extracts the fenced
`python` block before running `ast.parse` on it. For `test`, output is
expected to be pure pytest code with no markdown fences. For `repo`,
output is prose markdown with 3 mandatory sections plus 2 conditional
ones — the verifier checks section headers but does not parse code.

---

## Project layout

```
assist-cli/
├── assist/
│   ├── cli/                  # Typer commands and entry point
│   ├── core/                 # Orchestrator, registry, verifier, analyzers, builders
│   ├── agents/               # 7 specialized agents (one per task)
│   ├── llm/                  # LLM client factory and adapters
│   ├── schemas/              # Pydantic models (TaskInput, AgentOutput, GitDiff, ...)
│   ├── skills/               # Declarative skills (.md with YAML frontmatter v2.5)
│   └── utils/                # File I/O and helpers
├── config/
│   ├── registry.yaml         # Command → agent + skills mapping
│   └── settings.yaml         # Model, temperature, quality threshold
├── docs/
│   └── SKILL_FORMAT.md       # v2.5 Hybrid Canonical specification
├── tests/
│   ├── integration/          # End-to-end pipeline tests (6 tests)
│   └── unit/                 # Component-level tests (62 tests)
├── pyproject.toml
├── TECH_DEBT.md              # Known limitations and v0.3.0 roadmap items
└── README.md
```

---

## Testing

```bash
pytest
```

The 68 tests cover:

- **Integration tests** (6) — end-to-end pipelines (review, generate,
  refactor, test, diff, repo) with a `SequencedMockLLM` that simulates the
  self-validation loop deterministically. Shared analyzer fixtures live
  in `tests/integration/conftest.py`.
- **Agent unit tests** (21) — three tests per agent for `generate_draft`,
  `self_check`, `correct` in isolation, with prompt-construction
  verification.
- **Core unit tests** (30+) — one per analyzer, plus verifier,
  prompt_builder, prompt_context_builder, registry, skill_resolver,
  git_diff_extractor.
- **Schema tests** (4) — Pydantic model contracts.
- **Utility tests** (10+) — file readers, file metadata, mock LLM client.
- **CLI smoke test** (1).

All tests run without API calls thanks to mock LLM clients. Total runtime
is under 6 seconds.

To run with coverage:

```bash
pytest --cov=assist
```

---

## Tech stack

- **Python 3.10+** (tested on 3.13)
- **Typer** — CLI framework
- **Pydantic v2** — typed data contracts between modules
- **Rich** — terminal rendering (panels, tables, syntax highlighting)
- **PyYAML** — registry and skill frontmatter parsing
- **Anthropic SDK** — LLM client (Claude)
- **pytest** — testing framework

---

## Status

Personal project, version **0.2.0**.

What works (validated end-to-end with real LLM calls):

- All 7 commands functional with quality scores ≥ 0.85 on typical input
- All 8 skills migrated to v2.5 Hybrid Canonical standard
- 68 tests green, no flaky tests
- Self-validation loop converges in 1-2 iterations on the happy path
- Static analysis layer aggregates correctly at both file and repository scope

What's planned for **0.3.0**:

- Configuration-driven agents: read skill frontmatter and apply settings
  automatically (max_tokens, persona, inject position)
- `FileReader` robustness on non-UTF-8 files
- `SkillResolver` package-relative path resolution (currently CWD-dependent)
- `Rich Console` output bypass on Windows pipe redirection
- Caching of static analysis results between consecutive invocations on
  the same file

See [`TECH_DEBT.md`](TECH_DEBT.md) for the full inventory of known
limitations with severity, area, proposed solutions, and current
workarounds. 13 open items, 2 resolved during 0.2.0.

---

## Known limitations

Honest about what the system does not do well right now (full details in
[`TECH_DEBT.md`](TECH_DEBT.md)):

- **Large projects (500+ files)** — `assist repo` scans every Python file
  in the project to aggregate code-quality metrics. On large codebases
  this adds 30-60s of latency before the LLM call.
- **Non-UTF-8 files** — `FileReader` raises `UnicodeDecodeError` on files
  not encoded as UTF-8. A single bad file can break the project scan for
  most tasks (mitigated in `repo` by silent skipping).
- **Windows output piping** — Rich Console fails on Unicode characters
  when stdout is redirected. Workaround documented in `TECH_DEBT.md`
  section 3.1.
- **CWD-dependent CLI** — `assist` must be invoked from the repository
  root because `SkillResolver` resolves paths relative to the current
  directory.
- **Rate limits** — Prompts can be large (15-25k tokens for medium files
  on `diff` and `repo`); the Anthropic API rate limit of 30k tokens/min
  is easy to hit on consecutive invocations.
- **Python only** — Analyzers are Python-specific, though the skill
  machinery is language-agnostic.
- **Single LLM provider** — Currently only Anthropic; the `LLMFactory` is
  designed to be extended.

None of these are blockers for typical use on medium-sized projects.

---

## License

MIT — see `LICENSE` for details.

---

## Author

Emanuele Pio De Bernardis
