# Assist CLI — Proof Engine

[![tests](https://github.com/emanuelepiodebernardis/Assist_CLI-V2/actions/workflows/tests.yml/badge.svg)](https://github.com/emanuelepiodebernardis/Assist_CLI-V2/actions/workflows/tests.yml)

AI code is 99% right. The 1% ships to production.

Proof Engine is the verification layer for AI-generated code: deterministic
evidence instead of another LLM opinion. It runs your code in a sandbox,
mutates it, and checks whether your tests actually catch the mutations. The
LLM explains the verdict and proposes a fix — it never decides the verdict.

```
Verdict = sandbox execution + mutation testing (deterministic evidence)
Explanation and fix = LLM (strong model), only after the verdict exists
```

Assist CLI also ships the earlier generation of tools it was built on:
seven LLM-agent commands (`review`, `generate`, `refactor`, `explain`,
`test`, `diff`, `repo`) with self-validation loops and declarative skills.
See [Legacy commands](#legacy-commands-review-generate-refactor-explain-test-diff-repo)
below.

---

## Bring your own model (or none at all)

The verdict engine is deterministic — the LLM never decides pass/fail.
That means Proof Engine is **model-agnostic**:

- `--provider anthropic` — Anthropic API (default)
- `--provider openai` — any OpenAI-compatible endpoint: OpenAI, **Ollama**,
  LM Studio, vLLM, Groq, Mistral, DeepSeek, OpenRouter... configure
  `llm.base_url` in `config/settings.yaml` (e.g. `http://localhost:11434/v1`)
- `--provider none` — **evidence-only mode**: no LLM calls at all. Sandbox
  execution + mutation testing + coverage still produce a full verdict with
  exit codes. No API key, no cost, works offline.
- `--provider mock` — deterministic fixtures for development and CI of the
  tool itself

Model quality only affects the optional extras (generated boundary/property
tests, explanations, proposed fixes) — never the verdict.

## Benchmark results

Numbers from `benchmark/run_benchmark.py`, run against a corpus of 8
realistic AI-style bugs (off-by-one, wrong boolean logic, missing early
return, wrong default, missing function call, wrong slice bound, wrong
arithmetic operator). Each bug ships with an "AI-style" test: a happy-path
test that **passes** against the buggy code, the way an AI assistant
tends to write it.

| Metric | Value |
| --- | --- |
| Cases | 8 |
| Detection rate (bug caught by mutation testing) | **100%** |
| Average mutation score of the AI-style tests | **44%** |

Detection rate 100% means: on every one of the 8 cases, mutation testing
produced a surviving mutant that points at the exact bug line, even though
the existing test suite was green. Average mutation score 44% means: your
green tests, on average, prove less than half of what you think they do —
mutation testing kills a mutant on a given line only if a test actually
exercises the boundary that line represents.

Full per-case table (verdict, mutation score, detection, duration) is in
[`benchmark/results.md`](benchmark/results.md). Reproduce it locally:

```bash
python benchmark/run_benchmark.py
```

This runs with a mock LLM client (`generate_boundary_tests=False`): no API
calls, only deterministic evidence (existing tests + AST mutation testing).

---

## Quickstart

### Install

```bash
git clone https://github.com/emanuelepiodebernardis/Assist_CLI.git
cd Assist_CLI
pip install -e . pytest anthropic python-dotenv pyyaml
```

Set the API key (needed for boundary-test generation and the verdict
explanation, both LLM-assisted steps — the verdict itself is not):

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

### Verify a file

```bash
assist verify myfile.py
```

With no `--tests` flag, `assist verify` auto-discovers the test file using
pytest conventions (`TestDiscovery`, walking up to the project root). If
`myfile.py` imports local modules, those are copied into the sandbox
automatically (`DependencyCollector`) so multi-file projects work without
extra flags.

Exit code is CI-friendly: `0` unless the overall verdict is `fail`, so
`assist verify` can gate a pipeline step directly.

### More examples

```bash
# Verify only the files touched by a diff, mutating only the changed lines
assist verify --diff HEAD~1

# Explicit baseline test file instead of auto-discovery
assist verify myfile.py --tests tests/test_myfile.py

# Report in plain language for a non-technical reader (no jargon)
assist verify myfile.py --audience non-dev

# Export a signed verification certificate (JSON, HMAC-SHA256 if
# ASSIST_SIGNING_KEY is set)
assist verify myfile.py --certificate out.json

# Save the markdown report instead of printing it
assist verify myfile.py -o report.md

# Use the mock provider (no API calls, for local/offline testing)
assist verify myfile.py --provider mock
```

### Install the automatic hooks

```bash
assist install-hooks --pre-commit --claude-code
```

Installs a git `pre-commit` hook that runs `assist verify` on staged
Python files (blocks the commit on `fail`), and/or a Claude Code
`PostToolUse` hook that runs `assist verify` right after every `Edit` /
`Write`. Details in [`docs/hooks.md`](docs/hooks.md).

### GitHub Action

A ready-to-use workflow (`.github/workflows/assist-verify.yml`) runs
`assist verify --diff` on every pull request and posts (or updates) a PR
comment with the verdict table and evidence details. Setup and comment
format documented in [`docs/github-action.md`](docs/github-action.md).

---

## How it works

The pipeline (`assist/verification/pipeline.py`) runs in eight steps:

```
1. Syntax check              ast.parse - fail fast on invalid Python
2. Semantic analysis         reuses the existing SemanticAnalyzer
3. Local dependencies        DependencyCollector copies local imports
                              into the sandbox for multi-file targets
4. Test discovery            auto-finds the test file if --tests is
                              not passed (pytest conventions)
5. Baseline tests in sandbox isolated-process run, timeout, JUnit XML
                              parsing of the result
6. Boundary tests (fast)     BoundaryTestAgent generates edge-case
                              tests with the fast model (haiku tier)
7. Mutation testing          AST mutators (comparisons, arithmetic,
                              booleans, off-by-one, slices, early
                              returns, missing calls, ...), each run
                              in the sandbox, results cached by
                              sha256(mutated source + tests + deps);
                              with --diff, only changed lines are
                              mutated
8. Verdict + fix loop        EvidenceJudge turns the evidence into a
                              pass / warn / fail verdict and an
                              explanation (strong model); on fail,
                              ValidatedFixLoop proposes a fix and
                              re-runs it in the sandbox - a fix is
                              only shown if it turns the failing
                              tests green
```

The status (`pass` / `warn` / `fail`) is computed from evidence — test
results and mutation score against a threshold — before any LLM is
called for the verdict text. The strong model explains and can fix; it
does not get a vote on the status.

---

## Why evidence beats opinion

Most "AI code review" tools work the same way under the hood: an LLM
reads the diff and produces an opinion — a list of things it thinks might
be wrong. That opinion is graded by nothing but itself. There is no
independent signal telling you whether the LLM actually caught the bug or
just produced text that sounds like a review. When the code and the
reviewer are both LLM output, agreement between them proves nothing.

Proof Engine replaces that opinion with something that can be wrong in a
falsifiable way: run the code, mutate it, and see if the tests notice. A
surviving mutant is not an opinion — it is a specific line of code that
changed behavior without any test failing. That is the same signal a
human reviewer would look for by hand, produced mechanically and
consistently on every run.

The benchmark numbers above are the concrete version of this argument: on
all 8 cases the existing "AI-style" tests were green, and an LLM reviewer
skimming the diff has no structural reason to notice the bug. Mutation
testing found it every time, because it does not read the code for
plausibility — it checks whether the tests would actually fail if the
code were wrong.

---

## Architecture

```
                        assist verify <file> [--diff <range>]
                                   |
                     VerificationPipeline (assist/verification/)
                                   |
        +------------+------------+------------+------------------+
        |            |            |            |                  |
     syntax      semantic      local deps   test discovery         |
     (ast)       analysis      (sandbox     (pytest                |
                               multi-file)  conventions)            |
        |            |            |            |                  |
        +------------+------------+------------+------------------+
                                   |
                       SandboxRunner (isolated process, timeout)
                          baseline tests -> boundary tests
                                   |
                     MutationEngine (AST mutators + cache)
                                   |
                       EvidenceJudge (strong model)
                        pass / warn / fail + explanation
                                   |
                    fail? -> ValidatedFixLoop (strong model)
                             fix accepted only if sandbox-verified
                                   |
        +-----------+-----------+-----------+------------------+
        |           |           |           |                  |
    markdown    pr-comment   certificate  telemetry (stderr:
    report      (GitHub PR   (signed       phase times, LLM
                 comment)     JSON)         calls, cache hits)
```

### Commands

| Command | Purpose |
| --- | --- |
| `assist verify <file>` | Evidence-based verification (Proof Engine) |
| `assist install-hooks` | Install pre-commit and/or Claude Code hooks |
| `assist review <file>` | Technical review with concrete fixes |
| `assist generate <file>` | Generate Python code from a text specification |
| `assist refactor <file>` | Refactor code while preserving behavior |
| `assist explain <file>` | Technical explanation anchored to project context |
| `assist test <file>` | Generate a pytest test suite for a target file |
| `assist diff [range]` | Review a git diff (commit, range, working tree) |
| `assist repo [path]` | High-level overview of an entire repository |

### `assist verify` options

| Option | Values | Purpose |
| --- | --- | --- |
| `<file>` (arg) | path | File to verify (omit if using `--diff`) |
| `--tests`, `-t` | path | Baseline test file (auto-discovery if omitted) |
| `--diff` | git range | Verify touched files, mutate only changed lines |
| `--provider` | `anthropic` \| `mock` | LLM provider |
| `--format` | `markdown` \| `pr-comment` | Report format |
| `--audience` | `dev` \| `non-dev` | Jargon-free explanations for non-devs |
| `--output`, `-o` | path | Save the report to a file |
| `--certificate` | path | Export a signed verification certificate (JSON) |

---

## Legacy commands (review, generate, refactor, explain, test, diff, repo)

Seven commands, one specialized LLM agent per task, predating Proof
Engine. Each runs through: static analysis (8 analyzers: project
structure, dependency graph, cycles, health score, architectural risk,
semantic facts, cross-file usage, code quality) → agent self-validation
loop (`generate_draft` / `self_check` / `correct`) → `GlobalVerifier`
(syntax, non-empty, placeholders, task-aware checks) → formatted output.

```bash
assist review path/to/module.py                 # technical review
assist explain path/to/module.py --depth brief   # brief | verbose
assist refactor path/to/module.py --target readability
assist generate output_file.py --prompt "..."
assist test path/to/module.py                    # pytest suite
assist diff HEAD~3                                # or main..feature, --cached
assist repo .                                     # repository-level overview
```

All accept `--format terminal|markdown|json` and `--output <path>`. Every
output carries a quality score (0.0-1.0) from a deterministic rubric, a
verification table, and the self-correction iteration count that produced
it. These agents are opinion-producing (they read code and write prose or
new code); `verify` is evidence-producing. Use `review`/`explain`/`repo`
to understand and discuss code, use `verify` to decide whether it ships.

Eight declarative skills (`assist/skills/`, YAML frontmatter v2.5) encode
the rules each agent follows — style, review severity calibration,
refactor's behavioral-invariance protocol, pytest AAA conventions, and so
on. Format spec: [`docs/SKILL_FORMAT.md`](docs/SKILL_FORMAT.md).

What it is **not**: a chat assistant (no memory between invocations), a
generic LLM wrapper (every call applies structural constraints and
verifiable gates), a linter (static analysis is infrastructure, not the
final output), or an autonomous agent (it produces text/code for you to
review — executing changes stays a human decision).

---

## Project layout

```
assist-cli/
├── assist/
│   ├── cli/                  # Typer commands and entry point
│   ├── core/                 # Orchestrator, registry, verifier, analyzers
│   ├── agents/                # 7 legacy agents (one per task)
│   ├── llm/                   # LLM client factory and adapters (fast/strong)
│   ├── schemas/                # Pydantic models
│   ├── skills/                  # Declarative skills (.md, YAML frontmatter)
│   ├── utils/                    # File I/O and helpers
│   └── verification/              # Proof Engine: sandbox, mutation, judge,
│                                    fix loop, certificate, hooks, telemetry
├── benchmark/
│   ├── corpus/                # 8 realistic-bug cases with AI-style tests
│   ├── run_benchmark.py
│   └── results.md
├── config/
│   ├── registry.yaml          # Command -> agent + skills mapping
│   └── settings.yaml          # Models (fast/strong), thresholds
├── docs/
│   ├── SKILL_FORMAT.md
│   ├── hooks.md
│   ├── github-action.md
│   └── saas-architecture.md   # Phase 3 SaaS design
├── .github/workflows/assist-verify.yml
├── tests/                     # 294 tests, unit + integration
├── ROADMAP.md
└── README.md
```

## Testing

```bash
pytest
```

294 tests, no flaky tests, no API calls required (mock LLM clients and a
`MockLLMClient` for the benchmark). Run with coverage: `pytest --cov=assist`.

## Roadmap and further reading

- [`ROADMAP.md`](ROADMAP.md) — phased plan from Assist CLI to Proof Engine
- [`docs/hooks.md`](docs/hooks.md) — pre-commit and Claude Code hooks
- [`docs/github-action.md`](docs/github-action.md) — PR verification workflow
- [`docs/saas-architecture.md`](docs/saas-architecture.md) — Phase 3 SaaS design
- [`TECH_DEBT.md`](TECH_DEBT.md) — known limitations, severity, workarounds

## Tech stack

Python 3.10+, Typer, Pydantic v2, Rich, PyYAML, Anthropic SDK, pytest.

## License

MIT — see `LICENSE` for details.

## Author

Emanuele Pio De Bernardis

## License

Apache License 2.0 — see [LICENSE](LICENSE).
