"""Benchmark BM-1: mutation score del Proof Engine su codice reale.

Il benchmark in ``benchmark/run_benchmark.py`` misura il Proof Engine
su un corpus SINTETICO (bug iniettati ad arte, test scritti per
l'occasione). Questo script risponde a una domanda diversa: qual e'
il mutation score dei test REALI di progetti open source veri,
misurato dalla nostra pipeline in modalita' evidence-only (nessuna
chiamata LLM, ``NullLLMClient`` sia per il modello fast che per lo
strong)?

Metodologia
------------
1. Alcuni progetti Python piccoli e noti vengono clonati (shallow,
   ``--depth 1``) in ``/tmp/realworld`` (fuori da questo repo: lo
   script NON scrive nulla li', si limita a leggerli). Il commit
   esatto usato viene letto a runtime con ``git rev-parse HEAD`` nella
   directory clonata, cosi' il report riflette sempre cio' che e'
   stato davvero eseguito.
2. Per ogni progetto si scelgono coppie (modulo, file di test reale)
   con poche o nessuna dipendenza esterna, cosi' il modulo puo' girare
   da solo nella sandbox della pipeline. La pipeline, per ogni file
   target, copia il sorgente come ``<stem>.py`` e il test accanto, in
   una directory temporanea isolata; le dipendenze locali (stesso
   pacchetto) vengono raccolte automaticamente da
   ``DependencyCollector`` seguendo gli import nella directory reale
   del modulo.
3. VINCOLO NOTO: i test reali dei progetti scelti importano il modulo
   con import a pacchetto (es. ``from boltons.mathutils import
   clamp``), che nella sandbox flat non risolve (non esiste un
   pacchetto ``boltons``, solo ``mathutils.py``). L'UNICA modifica
   applicata ai file di terze parti e' quindi la riscrittura delle
   righe di import nei file di TEST (mai nel modulo sorgente), per
   renderle flat. Ogni riscrittura e' elencata esplicitamente nel
   campo ``rewrite`` di ogni ``Pair`` qui sotto ed e' riportata anche
   nel report finale. Lo script verifica a runtime che ogni pattern di
   riscrittura sia effettivamente presente nel file (altrimenti fallisce
   rumorosamente, cosi' un drift upstream non passa inosservato).
4. Ogni coppia e' stata verificata anche con un run pytest manuale
   indipendente (fuori da questo script, in una tempdir separata)
   prima di essere inclusa nella lista ``COPPIE``.

La pipeline gira con ``fast_llm=NullLLMClient(), strong_llm=
NullLLMClient()`` (evidence-only), ``generate_boundary_tests=False``
(si misura solo il test set REALE del progetto, non test sintetici
generati da noi) e ``max_mutants=25``.

Uso
---
Ogni run della pipeline su un modulo reale richiede alcuni secondi
(10-20s), quindi lo script processa le coppie a blocchi::

    cd /tmp/Assist_CLI
    python benchmark/run_realworld.py list
    python benchmark/run_realworld.py run boltons__mathutils
    python benchmark/run_realworld.py run boltons__listutils boltons__setutils
    python benchmark/run_realworld.py run all      # tutte, a blocchi
    python benchmark/run_realworld.py merge        # assembla il report

``run`` salva un JSON parziale per coppia in
``benchmark/realworld_partial/<nome>.json`` (idempotente: si puo'
rilanciare solo sulle coppie mancanti). ``merge`` legge tutti i
parziali disponibili e rigenera il report; puo' essere richiamato
piu' volte via via che nuove coppie vengono processate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from assist.llm.null_client import NullLLMClient  # noqa: E402
from assist.verification.pipeline import VerificationPipeline  # noqa: E402

REALWORLD_ROOT = Path("/tmp/realworld")
PARTIAL_DIR = Path(__file__).resolve().parent / "realworld_partial"
RESULTS_PATH = Path(__file__).resolve().parent / "realworld_results.md"

MAX_MUTANTS = 25
# Timeout basso per singola run pytest in sandbox: alcuni mutanti
# (es. flip di una condizione di while) possono introdurre loop
# infiniti nel codice reale; un timeout stretto li killa in fretta
# invece di far scadere il default (30s) per ognuno.
SANDBOX_TIMEOUT = 6


@dataclass(frozen=True)
class Pair:
    """Una coppia (modulo reale, test reale) candidata al benchmark.

    ``rewrite`` contiene le sostituzioni ESATTE applicate SOLO alle
    righe di import del file di test (mai al modulo sorgente), per
    farlo girare con l'import flat richiesto dalla sandbox della
    pipeline. Vedi il docstring del modulo per i dettagli.
    """

    project: str
    url: str
    module: str
    test: str
    rewrite: tuple[tuple[str, str], ...]
    name: str = ""


def _mk(
    project: str,
    url: str,
    module: str,
    test: str,
    rewrite: list[tuple[str, str]],
) -> Pair:
    stem = Path(module).stem
    return Pair(
        project=project,
        url=url,
        module=module,
        test=test,
        rewrite=tuple(rewrite),
        name=f"{project}__{stem}",
    )


COPPIE: list[Pair] = [
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/mathutils.py",
        "boltons/tests/test_mathutils.py",
        [("from boltons.mathutils import", "from mathutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/listutils.py",
        "boltons/tests/test_listutils.py",
        [("from boltons.listutils import", "from listutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/setutils.py",
        "boltons/tests/test_setutils.py",
        [("from boltons.setutils import", "from setutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/typeutils.py",
        "boltons/tests/test_typeutils.py",
        [("from boltons.typeutils import", "from typeutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/queueutils.py",
        "boltons/tests/test_queueutils.py",
        [("from boltons.queueutils import", "from queueutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/dictutils.py",
        "boltons/tests/test_dictutils.py",
        [("from boltons.dictutils import", "from dictutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/statsutils.py",
        "boltons/tests/test_statsutils.py",
        [("from boltons.statsutils import", "from statsutils import")],
    ),
    _mk(
        "boltons",
        "https://github.com/mahmoud/boltons.git",
        "boltons/boltons/strutils.py",
        "boltons/tests/test_strutils.py",
        [("from boltons import strutils", "import strutils")],
    ),
    _mk(
        "humanize",
        "https://github.com/jmoiron/humanize.git",
        "humanize/src/humanize/filesize.py",
        "humanize/tests/test_filesize.py",
        [("import humanize", "import filesize as humanize")],
    ),
    _mk(
        "toolz",
        "https://github.com/pytoolz/toolz.git",
        "toolz/toolz/utils.py",
        "toolz/toolz/tests/test_utils.py",
        [("from toolz.utils import", "from utils import")],
    ),
]

_COPPIE_BY_NAME = {pair.name: pair for pair in COPPIE}


@dataclass
class MutantSummary:
    lineno: int
    description: str


@dataclass
class PairResult:
    name: str
    project: str
    module: str
    commit: str
    error: str = ""
    verdict: str = ""
    baseline_passed: bool | None = None
    tests_collected: int = 0
    tests_failed: int = 0
    total_mutants: int = 0
    killed: int = 0
    mutation_score: float | None = None
    surviving: list[MutantSummary] = field(default_factory=list)
    duration_seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        data = dict(self.__dict__)
        data["surviving"] = [
            {"lineno": m.lineno, "description": m.description}
            for m in self.surviving
        ]
        return data

    @staticmethod
    def from_json(data: dict) -> PairResult:
        surviving = [
            MutantSummary(lineno=m["lineno"], description=m["description"])
            for m in data.get("surviving", [])
        ]
        kwargs = {**data, "surviving": surviving}
        return PairResult(**kwargs)


def _git_commit(project_dir: Path) -> str:
    """Legge il commit HEAD del repo clonato (a runtime, mai hardcoded)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip()
    except Exception as exc:  # repo assente o non e' un git repo
        return f"<sconosciuto: {exc}>"


def _apply_rewrite(test_source: str, rewrite: tuple[tuple[str, str], ...]) -> str:
    """Applica le sostituzioni di import al sorgente del test.

    Fallisce rumorosamente se un pattern atteso non e' presente: un
    progetto upstream aggiornato potrebbe aver cambiato gli import,
    e vogliamo accorgercene invece di eseguire silenziosamente un
    test non riscritto (che fallirebbe per ImportError comunque, ma
    con un messaggio meno chiaro).
    """
    for old, new in rewrite:
        if old not in test_source:
            raise RuntimeError(
                f"pattern di import atteso non trovato: {old!r}"
            )
        test_source = test_source.replace(old, new)
    return test_source


def run_pair(pair: Pair) -> PairResult:
    """Esegue la pipeline evidence-only su una singola coppia reale."""
    project_dir = REALWORLD_ROOT / pair.project
    module_path = REALWORLD_ROOT / pair.module
    test_path = REALWORLD_ROOT / pair.test
    commit = _git_commit(project_dir)

    result = PairResult(
        name=pair.name,
        project=pair.project,
        module=pair.module,
        commit=commit,
    )

    if not module_path.exists() or not test_path.exists():
        result.error = (
            f"file mancante: modulo={module_path.exists()} "
            f"test={test_path.exists()} (progetto clonato in "
            f"{REALWORLD_ROOT}?)"
        )
        return result

    try:
        test_source = test_path.read_text(encoding="utf-8")
        rewritten = _apply_rewrite(test_source, pair.rewrite)
    except Exception as exc:
        result.error = f"riscrittura import fallita: {exc}"
        return result

    with tempfile.TemporaryDirectory(prefix="realworld_bm_") as tmp:
        rewritten_test_path = Path(tmp) / test_path.name
        rewritten_test_path.write_text(rewritten, encoding="utf-8")

        pipeline = VerificationPipeline(
            fast_llm=NullLLMClient(),
            strong_llm=NullLLMClient(),
            max_mutants=MAX_MUTANTS,
            generate_boundary_tests=False,
            sandbox_timeout=SANDBOX_TIMEOUT,
        )

        start = time.monotonic()
        try:
            output = pipeline.run(
                file_path=str(module_path),
                tests_path=str(rewritten_test_path),
            )
        except Exception as exc:
            result.error = f"pipeline.run() ha sollevato: {exc}"
            return result
        result.duration_seconds = time.monotonic() - start

    result.verdict = output.verdict.status
    result.notes = list(output.evidence.notes)

    baseline = output.evidence.baseline_tests
    if baseline is not None:
        result.baseline_passed = baseline.passed
        result.tests_collected = baseline.tests_collected
        result.tests_failed = baseline.tests_failed
    else:
        result.error = "nessuna evidenza baseline_tests (test non eseguiti)"

    mutation = output.evidence.mutation
    if mutation is not None and not mutation.skipped_reason:
        result.total_mutants = mutation.total_mutants
        result.killed = mutation.killed
        result.mutation_score = mutation.mutation_score
        result.surviving = [
            MutantSummary(
                lineno=survivor.mutant.lineno,
                description=survivor.mutant.description,
            )
            for survivor in mutation.surviving_mutants[:3]
        ]
    elif mutation is not None:
        result.error = result.error or f"mutation saltato: {mutation.skipped_reason}"

    return result


def _save_partial(result: PairResult) -> Path:
    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PARTIAL_DIR / f"{result.name}.json"
    out_path.write_text(
        json.dumps(result.to_json(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def _load_partials() -> dict[str, PairResult]:
    results: dict[str, PairResult] = {}
    if not PARTIAL_DIR.exists():
        return results
    for path in sorted(PARTIAL_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result = PairResult.from_json(data)
        results[result.name] = result
    return results


def _fmt_score(score: float | None) -> str:
    return f"{score:.0%}" if score is not None else "n/d"


def render_markdown(results: dict[str, PairResult]) -> str:
    lines = [
        "# Benchmark BM-1 — mutation score su codice reale",
        "",
        "Misura il mutation score dei test REALI di progetti open",
        "source terzi tramite `VerificationPipeline` in modalita'",
        "evidence-only (`NullLLMClient` per fast e strong, nessuna",
        "chiamata LLM, `generate_boundary_tests=False`,",
        f"`max_mutants={MAX_MUTANTS}`). Nessun test e' generato da noi:",
        "il mutation score misurato e' quello del test set scritto",
        "dai manutentori originali del progetto.",
        "",
        f"Coppie definite: {len(COPPIE)} — coppie con risultato: "
        f"{len(results)}",
        "",
        "## Risultati",
        "",
        "| Coppia (progetto@commit) | Modulo | Verdetto | Test | "
        "Mutanti totali | Mutation score | Primi 3 mutanti sopravvissuti |",
        "|---|---|---|---|---|---|---|",
    ]

    scores: list[float] = []
    projects: set[str] = set()

    for pair in COPPIE:
        result = results.get(pair.name)
        if result is None:
            lines.append(
                f"| {pair.project}@n/d | {Path(pair.module).name} | "
                "*non eseguita* | - | - | - | - |"
            )
            continue

        commit_short = result.commit[:10]
        coppia_label = f"{result.project}@{commit_short}"
        modulo_label = Path(result.module).name

        if result.error:
            lines.append(
                f"| {coppia_label} | {modulo_label} | ERRORE | "
                f"{result.error} | - | - | - |"
            )
            continue

        projects.add(result.project)

        test_label = (
            f"{result.tests_collected - result.tests_failed}/"
            f"{result.tests_collected} pass"
        )

        survivors = "; ".join(
            f"L{m.lineno}: {m.description}" for m in result.surviving
        ) or "-"

        score_label = _fmt_score(result.mutation_score)
        if result.mutation_score is not None:
            scores.append(result.mutation_score)

        lines.append(
            f"| {coppia_label} | {modulo_label} | {result.verdict} | "
            f"{test_label} | {result.total_mutants} | {score_label} | "
            f"{survivors} |"
        )

    avg = sum(scores) / len(scores) if scores else 0.0
    lines += [
        "",
        f"Mutation score medio (su {len(scores)} coppie con mutation "
        f"testing eseguito): **{avg:.1%}**",
        f"Progetti distinti rappresentati: {len(projects)} "
        f"({', '.join(sorted(projects)) or 'nessuno'})",
        "",
        "## Metodologia",
        "",
        "1. Progetti clonati shallow (`git clone --depth 1`) in "
        "`/tmp/realworld`. Il commit riportato in tabella e' letto a "
        "runtime con `git rev-parse HEAD` nella directory clonata: "
        "riflette sempre cio' che e' stato davvero eseguito, non un "
        "valore fissato nello script. Nota: un clone shallow rifatto "
        "in un altro momento puo' prendere un commit piu' recente se "
        "l'upstream e' cambiato; per una riproduzione bit-per-bit "
        "servirebbe un clone completo seguito da "
        "`git checkout <commit>`.",
        "2. Per ogni coppia, la pipeline gira con "
        "`fast_llm=NullLLMClient(), strong_llm=NullLLMClient()` "
        f"(evidence-only), `generate_boundary_tests=False`, "
        f"`max_mutants={MAX_MUTANTS}`: nessun LLM coinvolto, il "
        "mutation score misura esclusivamente il test set reale del "
        "progetto.",
        "3. **Riscrittura import (unica modifica ai file di terze "
        "parti)**: i test reali usano import a pacchetto (es. "
        "`from boltons.mathutils import clamp`), che nella sandbox "
        "flat della pipeline non risolvono (viene copiato solo "
        "`<stem>.py`, non un pacchetto). Le uniche righe modificate "
        "sono le import dei file di TEST, mai il modulo sorgente. "
        "Le sostituzioni esatte per ogni coppia:",
        "",
    ]

    for pair in COPPIE:
        rewrite_desc = "; ".join(
            f"`{old}` -> `{new}`" for old, new in pair.rewrite
        )
        lines.append(f"   - `{pair.name}`: {rewrite_desc}")

    lines += [
        "",
        "4. Ogni coppia e' stata verificata anche con un run pytest "
        "manuale indipendente (fuori da questo script) prima di "
        "essere inclusa in `COPPIE`, per confermare che superasse i "
        "test dopo la sola riscrittura degli import.",
        "",
        "## Come riprodurre",
        "",
        "```bash",
        "mkdir -p /tmp/realworld && cd /tmp/realworld",
    ]

    for project in sorted({pair.project for pair in COPPIE}):
        url = next(p.url for p in COPPIE if p.project == project)
        lines.append(f"git clone --depth 1 {url}")

    lines += [
        "",
        "cd /tmp/Assist_CLI",
        "python benchmark/run_realworld.py list",
        "python benchmark/run_realworld.py run all",
        "python benchmark/run_realworld.py merge",
        "```",
        "",
        "Nota: le coppie con verdetto ERRORE indicano problemi di "
        "esecuzione (progetto non clonato, import driftato, test "
        "che non producono evidenza baseline) e sono escluse dal "
        "calcolo del mutation score medio.",
    ]

    return "\n".join(lines) + "\n"


def cmd_list(_args: argparse.Namespace) -> None:
    for pair in COPPIE:
        print(f"{pair.name}  ({pair.project}: {pair.module})")


def cmd_run(args: argparse.Namespace) -> None:
    names = list(_COPPIE_BY_NAME) if "all" in args.names else args.names

    unknown = [n for n in names if n not in _COPPIE_BY_NAME]
    if unknown:
        raise SystemExit(f"coppie sconosciute: {unknown}")

    for name in names:
        pair = _COPPIE_BY_NAME[name]
        print(f"--- {name} ---")
        result = run_pair(pair)
        out_path = _save_partial(result)
        status = result.error or result.verdict
        print(
            f"{name}: {status} "
            f"(score={_fmt_score(result.mutation_score)}, "
            f"{result.duration_seconds:.1f}s) -> {out_path}"
        )


def cmd_merge(_args: argparse.Namespace) -> None:
    results = _load_partials()
    markdown = render_markdown(results)
    RESULTS_PATH.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\nReport salvato in {RESULTS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="elenca le coppie definite")

    run_parser = sub.add_parser(
        "run", help="esegue la pipeline su una o piu' coppie"
    )
    run_parser.add_argument(
        "names",
        nargs="+",
        help="nomi delle coppie (o 'all' per tutte)",
    )

    sub.add_parser("merge", help="assembla realworld_results.md")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "merge":
        cmd_merge(args)


if __name__ == "__main__":
    main()
