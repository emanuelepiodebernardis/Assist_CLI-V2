from __future__ import annotations

from abc import ABC, abstractmethod

from assist.schemas.models import (
    AgentOutput,
    Skill,
    TaskInput,
    ValidationReport,
)


class BaseAgent(ABC):

    def __init__(
        self,
        llm,
        max_corrections: int = 1,
    ) -> None:

        self.llm = llm

        self.max_corrections = (
            max_corrections
        )

    def run(
        self,
        task: TaskInput,
        skills: list[Skill],
    ) -> AgentOutput:

        draft = self.generate_draft(
            task,
            skills,
        )

        final_report: (
            ValidationReport | None
        ) = None

        iterations_used = 0

        total_passes = (
            self.max_corrections + 1
        )

        for iteration in range(total_passes):

            iterations_used = (
                iteration + 1
            )

            final_report = (
                self.self_check(
                    draft,
                    task,
                    skills,
                )
            )

            if final_report.is_valid:
                break

            is_last_pass = (
                iteration
                == total_passes - 1
            )

            if is_last_pass:
                break

            draft = self.correct(
                draft,
                final_report,
                task,
                skills,
            )

        quality_score = (
            final_report.quality_score
            if final_report is not None
            else 0.0
        )

        return AgentOutput(
            content=draft,
            agent_name=(
                self.__class__.__name__
            ),
            task_type=task.command,
            quality_score=quality_score,
            iterations_used=iterations_used,
        )

    @abstractmethod
    def generate_draft(
        self,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def self_check(
        self,
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> ValidationReport:
        raise NotImplementedError

    @abstractmethod
    def correct(
        self,
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:
        raise NotImplementedError