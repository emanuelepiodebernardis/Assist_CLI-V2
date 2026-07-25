# Template: Agente base con self-validation loop
# Usa questo template come punto di partenza per un nuovo agente.
# Sostituisci TODO con l'implementazione specifica.

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from assist.llm.base import LLMClient
from assist.schemas.models import AgentOutput, TaskInput, ValidationReport

if TYPE_CHECKING:
    from assist.schemas.models import Skill

MAX_SELF_CORRECTIONS: int = 2
DEFAULT_QUALITY_THRESHOLD: float = 0.85


class BaseAgent(ABC):
    """Agente base con self-validation loop integrato.

    Tutti gli agenti specializzati ereditano da questa classe.
    L'implementazione del loop è qui: le sottoclassi implementano
    solo generate_draft() e self_check().

    Attributes:
        llm: Client LLM iniettato. Mai istanziato internamente.
        max_corrections: Numero massimo di iterazioni self-check.
        quality_threshold: Soglia minima di qualità accettabile.
    """

    def __init__(
        self,
        llm: LLMClient,
        max_corrections: int = MAX_SELF_CORRECTIONS,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    ) -> None:
        self.llm = llm
        self.max_corrections = max_corrections
        self.quality_threshold = quality_threshold

    def run(self, task: TaskInput, skills: list[Skill]) -> AgentOutput:
        """Esegue il task con self-validation loop.

        Args:
            task: Input strutturato con comando, file e opzioni.
            skills: Lista di skills caricate dal SkillResolver.

        Returns:
            AgentOutput con il miglior draft prodotto, quality_score
            e numero di iterazioni utilizzate.
        """
        draft = self.generate_draft(task, skills)
        best_draft = draft
        best_score = 0.0

        for iteration in range(self.max_corrections):
            report = self.self_check(draft, task)

            if report.quality_score > best_score:
                best_score = report.quality_score
                best_draft = draft

            if report.is_valid and report.quality_score >= self.quality_threshold:
                break

            draft = self._apply_corrections(draft, report, task, skills)

        return AgentOutput(
            content=best_draft,
            agent_name=self.__class__.__name__,
            task_type=task.command,
            quality_score=best_score,
            iterations_used=iteration + 1,
        )

    @abstractmethod
    def generate_draft(self, task: TaskInput, skills: list[Skill]) -> str:
        """Genera il primo draft dell'output.

        Args:
            task: Input strutturato.
            skills: Skills da iniettare nel prompt.

        Returns:
            Stringa con il draft dell'output.
        """
        ...

    @abstractmethod
    def self_check(self, draft: str, task: TaskInput) -> ValidationReport:
        """Valuta il draft con un prompt critico separato.

        IMPORTANTE: Questo metodo usa un prompt deliberatamente
        diverso da generate_draft. Non "controlla il tuo output":
        assume il ruolo di un reviewer esterno che non sa chi ha
        generato il draft.

        Args:
            draft: Output generato da valutare.
            task: Task originale, usato per verificare la coerenza.

        Returns:
            ValidationReport strutturato con score e issues.
        """
        ...

    def _apply_corrections(
        self,
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:
        """Applica le correzioni indicate nel report.

        Args:
            draft: Draft da correggere.
            report: Report con issues e azioni da applicare.
            task: Task originale per contesto.
            skills: Skills per il prompt di correzione.

        Returns:
            Draft corretto.
        """
        # TODO: costruire prompt di correzione da report.actions
        # e chiamare self.llm.complete(correction_prompt)
        raise NotImplementedError
