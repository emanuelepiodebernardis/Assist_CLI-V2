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

## Fase 3 — Prodotto (3-6 mesi)

- [ ] GitHub App SaaS (webhook PR, coda di verifica, dashboard)
- [ ] Sandbox containerizzata (Docker/gVisor) per codice non fidato
- [ ] Secondo linguaggio (TypeScript: mutazione via AST ts-morph, runner vitest/jest)
- [ ] "Certificato di verifica" esportabile (audit trail per compliance)
- [ ] Pricing: free per open source, per-seat + usage per team

## Metriche di successo

1. Mutation score medio dei test AI rilevato (baseline attesa: 30-60%)
2. % bug reali trovati che i reviewer LLM-only non trovano
3. % fix proposti accettati senza modifiche
4. Costo per verifica (target: < $0.05 con split fast/strong)
