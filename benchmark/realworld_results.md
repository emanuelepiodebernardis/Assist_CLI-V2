# Benchmark BM-1 — mutation score su codice reale

Misura il mutation score dei test REALI di progetti open
source terzi tramite `VerificationPipeline` in modalita'
evidence-only (`NullLLMClient` per fast e strong, nessuna
chiamata LLM, `generate_boundary_tests=False`,
`max_mutants=25`). Nessun test e' generato da noi:
il mutation score misurato e' quello del test set scritto
dai manutentori originali del progetto.

Coppie definite: 10 — coppie con risultato: 10

## Risultati

| Coppia (progetto@commit) | Modulo | Verdetto | Test | Mutanti totali | Mutation score | Primi 3 mutanti sopravvissuti |
|---|---|---|---|---|---|---|
| boltons@e66cade323 | mathutils.py | pass | 11/11 pass | 25 | 88% | L66: operatore di confronto < -> <=; L164: operatore di confronto > -> >=; L173: operatore di confronto >= -> > |
| boltons@e66cade323 | listutils.py | pass | 4/4 pass | 25 | 80% | L126: operatore di confronto > -> >=; L128: operatore di confronto > -> >=; L155: operatore di confronto == -> != |
| boltons@e66cade323 | setutils.py | pass | 9/9 pass | 25 | 76% | L146: operatore di confronto > -> >=; L148: operatore di confronto > -> >=; L154: operatore di confronto == -> != |
| boltons@e66cade323 | typeutils.py | warn | 3/3 pass | 16 | 31% | L80: negazione condizione if; L162: negazione condizione if; L100: operatore booleano or -> and |
| boltons@e66cade323 | queueutils.py | warn | 2/2 pass | 24 | 58% | L155: negazione condizione if; L167: negazione condizione if; L105: costante intera 0 -> 1 (off-by-one) |
| boltons@e66cade323 | dictutils.py | pass | 29/29 pass | 25 | 80% | L173: negazione condizione if; L254: negazione condizione if; L306: negazione condizione if |
| boltons@e66cade323 | statsutils.py | warn | 1/1 pass | 25 | 16% | L206: negazione condizione if; L204: negazione condizione if; L222: negazione condizione if |
| boltons@e66cade323 | strutils.py | pass | 19/19 pass | 25 | 64% | L108: negazione condizione if; L110: negazione condizione if; L140: negazione condizione if |
| humanize@87dfb1c03f | filesize.py | pass | 20/20 pass | 25 | 88% | L57: operatore di confronto < -> <=; L64: operatore di confronto < -> <=; L66: operatore di confronto < -> <= |
| toolz@568c2b8393 | utils.py | pass | 1/1 pass | 5 | 80% | L4: rimozione return anticipato |

Mutation score medio (su 10 coppie con mutation testing eseguito): **66.1%**
Progetti distinti rappresentati: 3 (boltons, humanize, toolz)

## Metodologia

1. Progetti clonati shallow (`git clone --depth 1`) in `/tmp/realworld`. Il commit riportato in tabella e' letto a runtime con `git rev-parse HEAD` nella directory clonata: riflette sempre cio' che e' stato davvero eseguito, non un valore fissato nello script. Nota: un clone shallow rifatto in un altro momento puo' prendere un commit piu' recente se l'upstream e' cambiato; per una riproduzione bit-per-bit servirebbe un clone completo seguito da `git checkout <commit>`.
2. Per ogni coppia, la pipeline gira con `fast_llm=NullLLMClient(), strong_llm=NullLLMClient()` (evidence-only), `generate_boundary_tests=False`, `max_mutants=25`: nessun LLM coinvolto, il mutation score misura esclusivamente il test set reale del progetto.
3. **Riscrittura import (unica modifica ai file di terze parti)**: i test reali usano import a pacchetto (es. `from boltons.mathutils import clamp`), che nella sandbox flat della pipeline non risolvono (viene copiato solo `<stem>.py`, non un pacchetto). Le uniche righe modificate sono le import dei file di TEST, mai il modulo sorgente. Le sostituzioni esatte per ogni coppia:

   - `boltons__mathutils`: `from boltons.mathutils import` -> `from mathutils import`
   - `boltons__listutils`: `from boltons.listutils import` -> `from listutils import`
   - `boltons__setutils`: `from boltons.setutils import` -> `from setutils import`
   - `boltons__typeutils`: `from boltons.typeutils import` -> `from typeutils import`
   - `boltons__queueutils`: `from boltons.queueutils import` -> `from queueutils import`
   - `boltons__dictutils`: `from boltons.dictutils import` -> `from dictutils import`
   - `boltons__statsutils`: `from boltons.statsutils import` -> `from statsutils import`
   - `boltons__strutils`: `from boltons import strutils` -> `import strutils`
   - `humanize__filesize`: `import humanize` -> `import filesize as humanize`
   - `toolz__utils`: `from toolz.utils import` -> `from utils import`

4. Ogni coppia e' stata verificata anche con un run pytest manuale indipendente (fuori da questo script) prima di essere inclusa in `COPPIE`, per confermare che superasse i test dopo la sola riscrittura degli import.

## Come riprodurre

```bash
mkdir -p /tmp/realworld && cd /tmp/realworld
git clone --depth 1 https://github.com/mahmoud/boltons.git
git clone --depth 1 https://github.com/jmoiron/humanize.git
git clone --depth 1 https://github.com/pytoolz/toolz.git

cd /tmp/Assist_CLI
python benchmark/run_realworld.py list
python benchmark/run_realworld.py run all
python benchmark/run_realworld.py merge
```

Nota: le coppie con verdetto ERRORE indicano problemi di esecuzione (progetto non clonato, import driftato, test che non producono evidenza baseline) e sono escluse dal calcolo del mutation score medio.
