# Roadmap — da Assist CLI a Proof Engine

Obiettivo: trasformare Assist CLI in un prodotto che **verifica con
evidenze deterministiche** il codice generato dall'AI, invece di
limitarsi a un'opinione LLM-su-LLM.

Principio architetturale: *lo status del verdetto lo decidono le
evidenze (sandbox, test, mutanti); l'LLM spiega e corregge, non giudica.*

## Fase 0 — Fondamenta (FATTO, v4.0)

- [x] Package `assist/verification/`: evidence, sandbox, mutation, boundary_agent, judge, pipeline
- [x] Sandbox a processo isolato con timeout (`SandboxRunner`)
- [x] Mutation engine AST (confronti, aritmetica, boolean, off-by-one)
- [x] Split modelli fast/strong (`LLMFactory.create_tier`, `config/settings.yaml`)
- [x] Comando `assist verify <file> [--tests ...]` con exit code CI-friendly
- [x] 19 test dedicati (158 totali verdi)

## Fase 1 — Robustezza locale (COMPLETATA, v4.3)

- [x] Scoperta automatica dei test esistenti (`TestDiscovery`, convenzioni pytest)
- [x] Supporto a progetti multi-file (`DependencyCollector`: import locali
  ricorsivi copiati nella sandbox)
- [x] Mutatore "negazione condizione if" + selezione mutanti per righe target
- [x] Loop di fix validato (`ValidatedFixLoop`): il fix e' accettato solo se
  i test rossi diventano verdi in sandbox, max N iterazioni con feedback errori
- [x] `assist verify --diff <range>`: verifica i file Python toccati,
  mutando solo le righe cambiate (`diff_targets`)
- [x] Parser strutturato dell'output pytest (JUnit XML built-in, fallback regex)
- [x] Mutatore "rimozione return anticipato" (con stack funzioni annidate)
- [x] Cache dei risultati per mutante (sha256 sorgente mutato+test+dipendenze)
- [x] Auto-quarantena dei test boundary flaky (doppio run di conferma)
- [x] Mutatori slice off-by-one e rimozione chiamata statement

## Fase 2 — Aggancio al flusso reale (COMPLETATA, v4.4)

- [x] GitHub Action + commento su PR (`.github/workflows/assist-verify.yml`,
  formato `--format pr-comment`, aggiornamento commento esistente)
- [x] Config per-repo `.assist.yaml`: soglie, esclusioni glob, budget mutanti
  (override dei default globali, ricerca risalendo alla project root)
- [x] Telemetria: tempi per fase, run sandbox, chiamate LLM fast/strong,
  cache hit (riga di riepilogo su stderr)
- [x] Esecuzione da qualunque directory (fallback config package + default)
- [x] Hook post-sessione: `assist install-hooks` (pre-commit git universale + PostToolUse Claude Code, merge idempotente di .claude/settings.json)
- [x] Report "non-developer": `--audience non-dev` (spiegazioni senza gergo, rischi in linguaggio quotidiano)

## Fase 3 — Prodotto (in corso, v4.5)

- [x] "Certificato di verifica" esportabile: `--certificate out.json`,
  payload con hash sorgente + evidenze, firma HMAC-SHA256
  (`ASSIST_SIGNING_KEY`), verifica anti-manomissione
- [x] Benchmark harness: corpus di 8 bug realistici con test-bugia,
  detection rate 100% (mutante sopravvissuto sulla riga del bug),
  mutation score medio dei test-bugia 44% (`benchmark/run_benchmark.py`)
- [x] Sandbox containerizzata: `DockerSandboxRunner` (--network=none,
  limiti cpu/mem, immagine configurabile) con fallback automatico a
  processo; flag `--docker` e config `verify.use_docker`
- [x] Design SaaS completo: `docs/saas-architecture.md` (GitHub App,
  coda, worker containerizzati, modello dati, sicurezza, costi, pricing,
  piano MVP 4-6 settimane)
- [x] README prodotto con benchmark reali (detection 100%, mutation
  score test-bugia 44%)
- [ ] Implementazione GitHub App SaaS (webhook PR, coda, dashboard)
- [ ] Secondo linguaggio (TypeScript: mutazione via AST ts-morph, runner vitest/jest)

## Metriche di successo

1. Mutation score medio dei test AI rilevato (baseline attesa: 30-60%)
2. % bug reali trovati che i reviewer LLM-only non trovano
3. % fix proposti accettati senza modifiche
4. Costo per verifica (target: < $0.05 con split fast/strong)


---

## Roadmap v2 (aggiornamento competitivo, luglio 2026)

Contesto: la sandbox execution si e' commoditizzata (Greptile TREX,
CodeRabbit fix-ci, Cursor pre-push, Copilot agentic). NESSUN player fa
mutation testing: la validazione dei test resta categoria vuota
(praticata solo internamente da Meta ACH e Google). Posizionamento:
"loro eseguono i test generati dall'AI; noi dimostriamo se quei test
valgono qualcosa". Vantaggio di costo strutturale: mutazione CPU-only
vs $2/run di TREX.

### Fase A — Velocita' e profondita' delle evidenze (COMPLETATA, v4.7)

- [x] Per-test coverage nel mutation engine (`coverage_map.py`:
  contexts per-test via pytest-cov, run mirati sui soli test che
  coprono la riga mutata; fallback trasparente)
- [x] Selezione euristica dei mutanti budget-aware:
  righe diff > confronti/negazioni > boolean > costanti > resto
- [x] Terza evidenza: property-based testing Hypothesis
  (`property_agent.py`, derandomize per determinismo, quarantena
  flaky, contribuisce anche al mutation testing)
- [x] Evidence artifacts nel commento PR: log sandbox e tabella
  completa dei mutanti in sezioni collassabili, colonna Fix

### Fase B — Espansione mercato (COMPLETATA, v4.8)

- [x] TypeScript via wrapper StrykerJS (`ts_support.py`: parser del
  mutation-testing-report-schema, availability check, docs/typescript.md)
- [x] Certificato come Statement in-toto v1 (`--intoto`, predicate
  `https://assist-cli.dev/verification/v1`, roundtrip firmato verificato)
- [x] Benchmark esteso a 20 casi, 8 categorie: detection rate 100%
  (20/20), mutation score medio dei test-bugia 44%

### Fase C — Prodotto

- [ ] GitHub App SaaS (design: docs/saas-architecture.md) con pricing
  aggressivo contro il $2/run di TREX (target < $0.05/verifica)
- [ ] Dashboard mutation score nel tempo (metrica che nessun
  competitor puo' mostrare)

### Non inseguire

Sandbox "stack-aware" con servizi reali (scala di TREX), browser/E2E
agentic testing (altro mercato), verifica formale completa (CrossHair
eventualmente come evidenza opzionale futura).


## v4.9 — Model-agnostic (luglio 2026)

- [x] Client OpenAI-compatible universale (`openai_compatible_client.py`,
  solo stdlib): OpenAI, Ollama, LM Studio, vLLM, Groq, Mistral,
  DeepSeek, OpenRouter e qualunque endpoint compatibile
- [x] Modalita' evidence-only `--provider none`: verdetto completo
  senza alcuna chiamata LLM (offline, zero costi) — possibile solo
  perche' il verdetto e' deterministico per architettura
- [x] Config `llm:` in settings.yaml (provider, base_url, api_key_env)
  con esempio Ollama documentato


## v5.0 — Multi-linguaggio: TypeScript nativo (luglio 2026)

- [x] Dispatch per estensione nella pipeline (.ts/.tsx/.js/.mjs)
- [x] `ts_runner.py`: vitest in sandbox Node (template node_modules
  via symlink, report JSON, ~0.7s per run)
- [x] `ts_test_agents.py`: boundary (vitest) e property (fast-check,
  configureGlobal numRuns) generati dal modello fast
- [x] Auto-discovery test TS (`.test.ts` / `.spec.ts`)
- [x] Stesso judge, report, certificato e telemetria del flusso
  Python: le evidenze sono language-agnostic per architettura
- [ ] Fix loop validato TS; dipendenze multi-file TS; mutation TS
  su file singolo (oggi via progetto StrykerJS)
- [ ] Prossimi linguaggi via wrapper: Java/Kotlin (PIT),
  C# (Stryker.NET), Rust (cargo-mutants), Go, PHP (Infection)
