"""Wrapper per mutation testing su TypeScript/JavaScript via StrykerJS.

Non scriviamo un mutation engine TS nostro: deleghiamo a StrykerJS
(https://stryker-mutator.io/), lo standard de facto per mutation
testing JS/TS, e convertiamo il suo report JSON (formato
mutation-testing-report-schema) nel nostro `MutationReport` interno.
Cosi' il resto della pipeline (soglie, verdetto, report Markdown)
resta identico tra target Python e TypeScript.

Prerequisiti per `run_stryker`: il progetto TS deve avere Stryker
gia' configurato (`stryker.conf.json`) e le dipendenze npm installate
(vedi `docs/typescript.md`). Questo modulo non installa nulla: si
limita a invocare l'eseguibile locale via `npx --no-install` e a
leggere il report che Stryker produce.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from assist.verification.evidence import Mutant, MutantResult, MutationReport

_MAX_DESCRIPTION_LEN = 80

_AVAILABILITY_TIMEOUT_SECONDS = 15

# Status Stryker (mutation-testing-report-schema) mappati sul nostro
# modello binario ucciso/sopravvissuto. "Ignored" non e' ne' l'uno
# ne' l'altro: e' un mutante scartato da Stryker stesso e va escluso
# dal conteggio totale.
_KILLED_STATUSES = {"Killed", "Timeout", "RuntimeError", "CompileError"}
_SURVIVED_STATUSES = {"Survived", "NoCoverage"}
_IGNORED_STATUSES = {"Ignored"}

_SURVIVED_DETAIL = (
    "I test passano anche con questa mutazione: "
    "il comportamento non e' verificato."
)
_NO_COVERAGE_DETAIL = "nessun test copre la riga"

# Cache di modulo: evita di rilanciare `node --version` / `npx
# stryker --version` (subprocess, qualche centinaio di ms l'uno) a
# ogni chiamata. `reset_ts_support_cache` la azzera per i test, cosi'
# ogni test parte da uno stato pulito indipendente dall'ordine di
# esecuzione.
_node_available_cache: bool | None = None
_stryker_available_cache: dict[str, bool] = {}


def reset_ts_support_cache() -> None:
    """Azzera le cache di modulo di `node_available`/`stryker_available`.

    Da chiamare nei test (es. in un fixture o a inizio test) per non
    dipendere da chiamate precedenti nello stesso processo.
    """

    global _node_available_cache
    _node_available_cache = None
    _stryker_available_cache.clear()


def node_available() -> bool:
    """Ritorna True se `node` e' eseguibile dal PATH corrente.

    Il risultato e' cachato a livello di modulo: vedi
    `reset_ts_support_cache`.
    """

    global _node_available_cache

    if _node_available_cache is not None:
        return _node_available_cache

    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            timeout=_AVAILABILITY_TIMEOUT_SECONDS,
            check=False,
        )
        _node_available_cache = result.returncode == 0
    except Exception:
        _node_available_cache = False

    return _node_available_cache


def stryker_available(project_dir: str | Path) -> bool:
    """Ritorna True se StrykerJS e' invocabile nella directory data.

    Esegue `npx --no-install stryker --version` con `cwd=project_dir`
    e timeout di 15s: exit code 0 significa che Stryker e' installato
    come dipendenza locale del progetto (`--no-install` impedisce a
    npx di tentare un download). Qualunque eccezione (timeout,
    comando assente, directory inesistente, ecc.) fa ritornare False
    invece di propagarsi. Il risultato e' cachato per directory: vedi
    `reset_ts_support_cache`.
    """

    key = str(Path(project_dir))

    if key in _stryker_available_cache:
        return _stryker_available_cache[key]

    try:
        result = subprocess.run(
            ["npx", "--no-install", "stryker", "--version"],
            cwd=key,
            capture_output=True,
            timeout=_AVAILABILITY_TIMEOUT_SECONDS,
            check=False,
        )
        available = result.returncode == 0
    except Exception:
        available = False

    _stryker_available_cache[key] = available
    return available


def parse_stryker_report(report_json: str) -> MutationReport:
    """Converte un report Stryker in un `MutationReport` interno.

    Legge il formato mutation-testing-report-schema di Stryker:
    ``{"files": {"<path>": {"mutants": [{"id", "mutatorName",
    "status", "location": {"start": {"line", ...}, ...},
    "replacement", ...}, ...]}}}``.

    Mappatura degli status:

    - "Killed", "Timeout", "RuntimeError", "CompileError" -> ucciso
      (il mutante e' stato rilevato, in un modo o nell'altro).
    - "Survived", "NoCoverage" -> sopravvissuto. Per "NoCoverage" il
      `detail` e' "nessun test copre la riga", coerente con la stessa
      situazione nel `MutationEngine` Python (`mutation.py`).
    - "Ignored" -> escluso dal conteggio totale: Stryker lo ha
      scartato a monte, non e' evidenza a favore ne' contro i test.

    Ogni mutante genera un `Mutant` con `mutant_id` progressivo,
    `lineno` da `location.start.line`, `description` nel formato
    ``f"{mutatorName}: {replacement}"`` troncata a 80 caratteri e
    `original_snippet` vuoto (Stryker non lo fornisce nel report
    JSON; lo snippet mutato resta nel report HTML di Stryker stesso).

    `mutation_score = killed / total` (arrotondato a 3 decimali).

    JSON malformato, non un oggetto, privo della chiave "files" o
    senza alcun mutante utile produce un `MutationReport` con
    `skipped_reason` valorizzato invece di sollevare un'eccezione.
    """

    try:
        data = json.loads(report_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return MutationReport(
            skipped_reason=f"Report Stryker non e' JSON valido: {exc}"
        )

    if not isinstance(data, dict):
        return MutationReport(
            skipped_reason="Report Stryker malformato: atteso un oggetto JSON."
        )

    files = data.get("files")
    if not isinstance(files, dict):
        return MutationReport(
            skipped_reason="Report Stryker malformato: manca la chiave 'files'."
        )

    killed = 0
    surviving: list[MutantResult] = []
    mutant_id = 0

    for file_data in files.values():
        if not isinstance(file_data, dict):
            continue

        raw_mutants = file_data.get("mutants")
        if not isinstance(raw_mutants, list):
            continue

        for raw in raw_mutants:
            if not isinstance(raw, dict):
                continue

            status = raw.get("status")
            if status in _IGNORED_STATUSES:
                continue

            mutant_id += 1

            location = raw.get("location") or {}
            start = location.get("start") or {}
            lineno = start.get("line") or 0

            mutator_name = raw.get("mutatorName", "")
            replacement = raw.get("replacement", "")
            description = f"{mutator_name}: {replacement}"
            description = description[:_MAX_DESCRIPTION_LEN]

            mutant = Mutant(
                mutant_id=mutant_id,
                lineno=lineno,
                description=description,
                original_snippet="",
            )

            if status in _KILLED_STATUSES:
                killed += 1
                continue

            if status == "NoCoverage":
                detail = _NO_COVERAGE_DETAIL
            elif status in _SURVIVED_STATUSES:
                detail = _SURVIVED_DETAIL
            else:
                # Status non previsto dallo schema: trattato come
                # sopravvissuto per prudenza (non possiamo confermare
                # che sia stato rilevato).
                detail = f"status Stryker non riconosciuto: {status!r}"

            surviving.append(
                MutantResult(mutant=mutant, killed=False, detail=detail)
            )

    total = killed + len(surviving)

    if total == 0:
        return MutationReport(
            skipped_reason="Il report Stryker non contiene mutanti da valutare."
        )

    return MutationReport(
        total_mutants=total,
        killed=killed,
        survived=total - killed,
        mutation_score=round(killed / total, 3),
        surviving_mutants=surviving,
    )


def run_stryker(
    project_dir: str | Path, timeout_seconds: int = 240
) -> MutationReport:
    """Esegue StrykerJS sul progetto TS e ne converte il report.

    Lancia ``npx --no-install stryker run --reporters json`` con
    `cwd=project_dir`, poi cerca il report in
    ``reports/mutation/mutation.json`` (path di default del reporter
    "json" di Stryker) e lo passa a `parse_stryker_report`.

    Il progetto in `project_dir` deve avere Stryker gia' configurato
    (file `stryker.conf.json` nella root) e le dipendenze npm
    installate (`@stryker-mutator/core` + il runner del test framework
    usato, es. `@stryker-mutator/vitest-runner`): vedi
    `docs/typescript.md` per un esempio minimo. Questa funzione non
    installa ne' configura nulla.

    Se Node o Stryker non sono disponibili, il comando va in timeout,
    fallisce, o non produce il report atteso, ritorna un
    `MutationReport` con `skipped_reason` valorizzato invece di
    sollevare un'eccezione: l'assenza del toolchain TS non deve far
    crashare la pipeline di verifica.
    """

    project_path = Path(project_dir)

    if not node_available():
        return MutationReport(
            skipped_reason="Node.js non disponibile nel PATH: impossibile "
            "eseguire StrykerJS."
        )

    if not stryker_available(project_path):
        return MutationReport(
            skipped_reason=(
                "StrykerJS non disponibile nel progetto "
                f"'{project_path}' (dipendenze npm mancanti o "
                "stryker.conf.json assente?)."
            )
        )

    report_path = project_path / "reports" / "mutation" / "mutation.json"

    try:
        subprocess.run(
            ["npx", "--no-install", "stryker", "run", "--reporters", "json"],
            cwd=project_path,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return MutationReport(
            skipped_reason=(
                f"Esecuzione di Stryker interrotta per timeout "
                f"({timeout_seconds}s)."
            )
        )
    except Exception as exc:
        return MutationReport(
            skipped_reason=f"Esecuzione di Stryker fallita: {exc}"
        )

    if not report_path.is_file():
        return MutationReport(
            skipped_reason=(
                "Stryker non ha prodotto il report atteso in "
                f"'{report_path}'. Controllare la configurazione "
                "(reporters: ['json']) e i log del comando."
            )
        )

    report_json = report_path.read_text(encoding="utf-8")
    return parse_stryker_report(report_json)
