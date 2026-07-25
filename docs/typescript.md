# Supporto TypeScript (via StrykerJS)

**Stato**: sperimentale (Fase B della roadmap). Copre **solo** il
mutation testing come evidenza, tramite un wrapper attorno a
StrykerJS. Non c'e' (ancora) un mutation engine TypeScript scritto da
zero: Assist CLI delega a Stryker, lo standard de facto per mutation
testing JavaScript/TypeScript, e ne converte il report nel formato
interno (`MutationReport`) usato dal resto della pipeline.

## Perche' un wrapper e non un motore proprio

Il `MutationEngine` Python (`assist/verification/mutation.py`) lavora
sull'AST di Python con `ast`/`ast.unparse`. Riscrivere un equivalente
per TypeScript (parsing, type-checking, generazione di varianti,
esecuzione) e' un progetto a se' e duplicherebbe uno strumento gia'
maturo. StrykerJS fa esattamente questo lavoro, ha un ecosistema di
runner per i principali test framework (Jest, Vitest, Mocha, Karma)
e produce un report JSON con uno schema stabile
(`mutation-testing-report-schema`), quindi il modo piu' pragmatico di
estendere Assist CLI a TS e' **eseguire Stryker e leggerne l'output**.

## Come funziona il wrapper

Modulo: `assist/verification/ts_support.py`.

- `node_available() -> bool` — verifica che `node` sia nel PATH
  (`node --version`, timeout 15s, cache di modulo).
- `stryker_available(project_dir) -> bool` — verifica che Stryker sia
  installato come dipendenza locale del progetto TS (esegue
  `npx --no-install stryker --version` con `cwd=project_dir`, timeout
  15s; qualunque errore ritorna `False`, mai un'eccezione). Anche
  questo risultato e' cachato, per directory.
- `run_stryker(project_dir, timeout_seconds=240) -> MutationReport` —
  esegue `npx --no-install stryker run --reporters json` nella
  directory del progetto, legge `reports/mutation/mutation.json` (il
  path di output di default del reporter `json`) e lo converte con
  `parse_stryker_report`.
- `parse_stryker_report(report_json: str) -> MutationReport` — parser
  puro (nessun I/O) del formato Stryker verso `MutationReport`.

Entrambe le funzioni di disponibilita' (`node_available`,
`stryker_available`) e l'esecuzione (`run_stryker`) sono **fail-safe**:
se il toolchain TS non e' presente o l'esecuzione fallisce, il
risultato e' un `MutationReport(skipped_reason=...)`, non
un'eccezione. La pipeline di verifica puo' quindi continuare (con
mutation testing "saltato" e motivo esplicito) anche su una macchina
senza Node/Stryker installati.

### Mappatura degli status Stryker

Stryker assegna a ogni mutante uno tra diversi status; il wrapper li
riduce al modello binario ucciso/sopravvissuto usato internamente:

| Status Stryker                              | Esito interno   | Note                                  |
|----------------------------------------------|-----------------|----------------------------------------|
| `Killed`, `Timeout`, `RuntimeError`, `CompileError` | ucciso    | il mutante e' stato rilevato           |
| `Survived`                                    | sopravvissuto   | i test passano comunque                |
| `NoCoverage`                                  | sopravvissuto   | `detail = "nessun test copre la riga"` |
| `Ignored`                                     | escluso dal totale | scartato da Stryker stesso, non conta |

`mutation_score = killed / total_mutants` (Ignored esclusi dal
totale), esattamente come per il `MutationEngine` Python: il resto
della pipeline (soglie, verdetto, report) non deve sapere se
l'evidenza viene da Python o da TypeScript.

## Cosa NON copre (ancora)

- **Nessun boundary test agent per TS**: `BoundaryTestAgent` genera
  test di confronto/limite solo per funzioni Python. Per TS bisogna
  gia' avere una suite di test (Vitest/Jest/Mocha) scritta a mano o
  generata a parte.
- **Nessun property-based testing per TS**: l'integrazione con
  Hypothesis (`property_agent.py`) resta specifica di Python; non
  c'e' equivalente fast-check/Vitest collegato automaticamente.
- **Nessun fix loop per TS**: `fix_loop.py` genera e valida patch
  Python in sandbox. Per TS il wrapper si limita a *misurare* (score
  di mutazione), non propone e non valida correzioni.
- **Solo mutation score come evidenza**: per TS, `EvidenceBundle.mutation`
  e' l'unica evidenza automatica disponibile. Non ci sono ancora
  `baseline_tests`/`boundary_tests`/`property_tests` popolati per
  target TypeScript nella pipeline (`pipeline.py` resta orientata a
  moduli Python; l'integrazione di `run_stryker` nel flusso `assist
  verify` e' un passo successivo).
- **Nessuna installazione automatica**: il wrapper non installa Node,
  Stryker ne' le dipendenze npm del progetto. Deve gia' esistere un
  `stryker.conf.json` funzionante e un `npm install` gia' eseguito.

## Prerequisiti

- Node.js disponibile nel PATH (verificato da `node_available()`).
- Nel progetto TS target:
  - `stryker.conf.json` (o `.mjs`/`.cjs`) configurato nella root.
  - `@stryker-mutator/core` e il runner del test framework usato
    installati come `devDependencies` (`npm install` gia' eseguito).
  - Una suite di test funzionante (Vitest/Jest/Mocha) che Stryker
    possa lanciare contro ogni mutante.

## Esempio minimo: `stryker.conf.json` con Vitest

```json
{
  "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
  "packageManager": "npm",
  "testRunner": "vitest",
  "reporters": ["json", "clear-text", "progress"],
  "coverageAnalysis": "perTest",
  "mutate": ["src/**/*.ts", "!src/**/*.test.ts"]
}
```

Dipendenze da installare nel progetto TS:

```bash
npm install --save-dev @stryker-mutator/core @stryker-mutator/vitest-runner vitest
```

Esecuzione manuale (per verificare la configurazione prima di
delegarla ad Assist CLI):

```bash
npx stryker run --reporters json
```

Il report finira' in `reports/mutation/mutation.json`, lo stesso path
che `run_stryker()` cerca automaticamente.

## Uso da codice

```python
from assist.verification.ts_support import run_stryker, stryker_available

if stryker_available("path/al/progetto-ts"):
    report = run_stryker("path/al/progetto-ts", timeout_seconds=240)
    print(report.mutation_score, report.skipped_reason)
```

Se preferisci partire da un report gia' generato (es. da CI):

```python
from pathlib import Path
from assist.verification.ts_support import parse_stryker_report

report_json = Path("reports/mutation/mutation.json").read_text()
report = parse_stryker_report(report_json)
```
