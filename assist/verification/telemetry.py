"""Telemetria della pipeline di verifica.

Raccoglie tempi di fase e contatori (run in sandbox, chiamate LLM,
cache hit del mutation testing) per diagnosticare i costi/performance
di una singola esecuzione della pipeline.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from pydantic import BaseModel, Field

from assist.llm.base import LLMClient


class PhaseTiming(BaseModel):
    """Durata misurata di una singola fase della pipeline."""

    name: str
    duration_seconds: float


class VerificationStats(BaseModel):
    """Statistiche aggregate di un'esecuzione della pipeline."""

    phases: list[PhaseTiming] = Field(default_factory=list)
    sandbox_runs: int = 0
    llm_calls_fast: int = 0
    llm_calls_strong: int = 0
    mutation_cache_hits: int = 0
    total_seconds: float = 0.0

    def summary_line(self) -> str:
        """Riga compatta di riepilogo per log/output CLI."""

        return (
            f"verifica in {self.total_seconds:.1f}s | "
            f"sandbox: {self.sandbox_runs} run | "
            f"LLM: {self.llm_calls_fast} fast + "
            f"{self.llm_calls_strong} strong | "
            f"cache: {self.mutation_cache_hits} hit"
        )


class Telemetry:
    """Raccoglitore di telemetria per una esecuzione della pipeline."""

    def __init__(self) -> None:
        self.stats = VerificationStats()

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Context manager che misura la durata di una fase.

        Al termine (anche in caso di eccezione) appende un
        ``PhaseTiming`` a ``self.stats.phases``.
        """

        start = time.monotonic()
        try:
            yield
        finally:
            duration = time.monotonic() - start
            self.stats.phases.append(
                PhaseTiming(name=name, duration_seconds=duration)
            )

    def count_sandbox_run(self) -> None:
        """Incrementa il contatore delle esecuzioni in sandbox."""

        self.stats.sandbox_runs += 1

    def count_llm_fast(self) -> None:
        """Incrementa il contatore delle chiamate al modello fast."""

        self.stats.llm_calls_fast += 1

    def count_llm_strong(self) -> None:
        """Incrementa il contatore delle chiamate al modello strong."""

        self.stats.llm_calls_strong += 1

    def count_mutation_cache_hit(self) -> None:
        """Incrementa il contatore delle cache hit del mutation testing."""

        self.stats.mutation_cache_hits += 1

    def finish(self) -> VerificationStats:
        """Calcola ``total_seconds`` come somma delle fasi e ritorna le stats."""

        self.stats.total_seconds = sum(
            phase.duration_seconds for phase in self.stats.phases
        )
        return self.stats


class CountingLLM(LLMClient):
    """Wrapper di un ``LLMClient`` che notifica ogni chiamata a ``complete``.

    Non modifica il client interno: delega semplicemente la chiamata e
    invoca ``on_call`` prima di restituire il risultato, così da poter
    contare le chiamate (es. per la telemetria) senza toccare i client
    esistenti.
    """

    def __init__(self, inner: LLMClient, on_call: Callable[[], None]) -> None:
        self.inner = inner
        self.on_call = on_call

    def complete(self, prompt: str, system: str = "") -> str:
        result = self.inner.complete(prompt, system=system)
        self.on_call()
        return result
