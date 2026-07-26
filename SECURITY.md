# Security — modello di isolamento della sandbox

Questo documento risponde alla domanda: *cosa può fare il codice
sotto verifica (inclusi i mutanti) durante l'esecuzione?*

## Sandbox a processo (default)

`SandboxRunner` esegue codice e test in un **sottoprocesso Python
separato**, in una **directory temporanea usa-e-getta** cancellata a
fine run, con **timeout** configurabile e ambiente minimale
(solo `PATH`, `PYTHONDONTWRITEBYTECODE`, `PYTHONIOENCODING`).

Cosa NON impedisce: accesso alla rete, lettura di file di sistema
leggibili dall'utente, uso di CPU/memoria entro il timeout.

**Adatta a: codice proprio o di fiducia** (il tuo repository, le tue
PR). E' lo stesso livello di fiducia di eseguire `pytest` in locale.

## Sandbox Docker (`--docker` o `verify.use_docker: true`)

`DockerSandboxRunner` esegue in un container con:

- `--network=none` — nessun accesso alla rete
- `--memory` e `--cpus` limitati (default 512m / 1 cpu)
- sorgenti montati **read-only**, lavoro su copia interna
- container `--rm` distrutto a fine run

**Adatta a: codice non fidato** (PR esterne, codice generato da
terzi). Se Docker non e' disponibile, il runner fa fallback alla
sandbox a processo **loggando un warning esplicito** — non
silenziosamente.

## Sandbox TypeScript

`TsSandboxRunner` esegue vitest in un sottoprocesso Node con
directory temporanea e timeout; `node_modules` e' un symlink
read-only al template. Stesso livello di isolamento della sandbox a
processo Python: per codice TS non fidato, usare un ambiente
containerizzato.

## Cosa vede l'LLM

Il modello riceve solo: il sorgente del file sotto verifica, i test,
e le evidenze (esiti, mutanti, log troncati). Mai l'intero repository.
In modalita' `--provider none` nessun dato lascia la macchina.

## Segnalazioni

Per vulnerabilita': aprire una security advisory su GitHub
(Security → Report a vulnerability) o contattare l'autore.
