"""Benchmark harness per le metriche di successo della ROADMAP.

Esegue la ``VerificationPipeline`` (Proof Engine) su un corpus di
casi con un bug noto ciascuno, usando provider LLM mock
(``MockLLMClient``) e ``generate_boundary_tests=False``: nessuna
chiamata a un LLM reale, contano solo le evidenze deterministiche
(run dei test esistenti + mutation testing su AST).

Per ogni caso il corpus fornisce dei "test-bugia": test che passano
anche col codice buggato (verificano il caso felice, non il
boundary del bug). La domanda a cui risponde il benchmark e': il
mutation engine riesce comunque a individuare la riga del bug,
segnalando un mutante sopravvissuto proprio li'?

Uso::

    cd /tmp/Assist_CLI
    python benchmark/run_benchmark.py

Il report viene stampato su stdout e salvato in
``benchmark/results.md``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from assist.llm.mock_client import MockLLMClient  # noqa: E402
from assist.verification.pipeline import VerificationPipeline  # noqa: E402

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
RESULTS_PATH = Path(__file__).resolve().parent / "results.md"

# Categorie di bug attese in un caso.yaml del corpus.
_CATEGORIE_VALIDE = frozenset(
    {
        "off_by_one",
        "boundary",
        "logica_booleana",
        "early_return",
        "slice",
        "chiamata_mancante",
        "aritmetica",
        "default_sbagliato",
    }
)


class CaseResult(BaseModel):
    """Esito della pipeline di verifica su un singolo caso del corpus."""

    name: str
    categoria: str
    verdict_status: str
    mutation_score: float | None = None
    mutants_survived_on_bug_line: bool = False
    duration_seconds: float = 0.0


class BenchmarkReport(BaseModel):
    """Aggregato dei risultati del benchmark su tutto il corpus."""

    cases: list[CaseResult] = Field(default_factory=list)
    detection_rate: float = 0.0
    avg_mutation_score: float = 0.0

    @property
    def totale_casi(self) -> int:
        """Numero totale di casi valutati."""
        return len(self.cases)

    def render_markdown(self) -> str:
        """Costruisce il report in markdown con la tabella dei risultati."""
        lines = [
            "# Benchmark Proof Engine — metriche di successo",
            "",
            f"Casi totali: {self.totale_casi}",
            f"Detection rate (bug individuato dal mutation testing): "
            f"{self.detection_rate:.0%}",
            f"Mutation score medio: {self.avg_mutation_score:.0%}",
            "",
            "| Caso | Categoria | Verdetto | Mutation score | "
            "Bug rilevato | Durata (s) |",
            "|---|---|---|---|---|---|",
        ]

        for case in self.cases:
            score = (
                f"{case.mutation_score:.0%}"
                if case.mutation_score is not None
                else "n/d"
            )
            rilevato = "si" if case.mutants_survived_on_bug_line else "no"
            lines.append(
                f"| {case.name} | {case.categoria} | "
                f"{case.verdict_status} | {score} | {rilevato} | "
                f"{case.duration_seconds:.2f} |"
            )

        return "\n".join(lines)


def _load_caso_yaml(path: Path) -> dict:
    """Legge e valida i campi richiesti di un ``caso.yaml``."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    campi_richiesti = ("name", "bug_description", "bug_line", "categoria")
    mancanti = [campo for campo in campi_richiesti if campo not in data]
    if mancanti:
        raise ValueError(f"{path}: campi mancanti {mancanti}")

    if data["categoria"] not in _CATEGORIE_VALIDE:
        raise ValueError(
            f"{path}: categoria non valida {data['categoria']!r}"
        )

    return data


def _run_case(case_dir: Path) -> CaseResult:
    """Esegue la pipeline di verifica su un singolo caso del corpus."""
    caso = _load_caso_yaml(case_dir / "caso.yaml")
    bug_line = int(caso["bug_line"])

    pipeline = VerificationPipeline(
        fast_llm=MockLLMClient(fixture="Spiegazione mock."),
        strong_llm=MockLLMClient(fixture="Spiegazione mock."),
        generate_boundary_tests=False,
        max_mutants=30,
        max_fix_iterations=1,
    )

    start = time.monotonic()
    output = pipeline.run(
        file_path=str(case_dir / "target.py"),
        tests_path=str(case_dir / "test_target.py"),
    )
    duration = time.monotonic() - start

    mutation = output.evidence.mutation
    mutation_score = (
        mutation.mutation_score
        if mutation and not mutation.skipped_reason
        else None
    )

    survived_on_bug_line = False
    if mutation:
        survived_on_bug_line = any(
            result.mutant.lineno == bug_line
            for result in mutation.surviving_mutants
        )

    return CaseResult(
        name=caso["name"],
        categoria=caso["categoria"],
        verdict_status=output.verdict.status,
        mutation_score=mutation_score,
        mutants_survived_on_bug_line=survived_on_bug_line,
        duration_seconds=duration,
    )


def run_benchmark() -> BenchmarkReport:
    """Scandisce ``benchmark/corpus`` ed esegue la pipeline su ogni caso."""
    case_dirs = sorted(p for p in CORPUS_DIR.iterdir() if p.is_dir())

    results = [_run_case(case_dir) for case_dir in case_dirs]

    totale = len(results)
    rilevati = sum(1 for r in results if r.mutants_survived_on_bug_line)
    detection_rate = rilevati / totale if totale else 0.0

    punteggi = [r.mutation_score for r in results if r.mutation_score is not None]
    avg_mutation_score = sum(punteggi) / len(punteggi) if punteggi else 0.0

    return BenchmarkReport(
        cases=results,
        detection_rate=detection_rate,
        avg_mutation_score=avg_mutation_score,
    )


def main() -> None:
    """Esegue il benchmark, stampa il report e lo salva su disco."""
    report = run_benchmark()
    markdown = report.render_markdown()

    print(markdown)

    RESULTS_PATH.write_text(markdown + "\n", encoding="utf-8")
    print(f"\nReport salvato in {RESULTS_PATH}")


if __name__ == "__main__":
    main()
