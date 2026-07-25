from __future__ import annotations

import json

from assist.agents.base import BaseAgent
from assist.core.prompt_builder import PromptBuilder
from assist.schemas.models import (
    Issue,
    Skill,
    TaskInput,
    ValidationReport,
)

ALLOWED_SEVERITIES: set[str] = {
    "critical",
    "high",
    "medium",
    "low",
}


SEVERITY_ALIASES: dict[str, str] = {
    "minor": "low",
    "trivial": "low",
    "info": "low",
    "informational": "low",
    "note": "low",
    "warning": "medium",
    "moderate": "medium",
    "major": "high",
    "severe": "high",
    "blocker": "critical",
    "fatal": "critical",
}


def _normalize_severity(
    raw: object,
) -> str:

    if not isinstance(raw, str):
        return "medium"

    value = raw.strip().lower()

    if value in ALLOWED_SEVERITIES:
        return value

    if value in SEVERITY_ALIASES:
        return SEVERITY_ALIASES[value]

    return "medium"


def _clamp_score(
    raw: object,
) -> float:

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0

    if value < 0.0:
        return 0.0

    if value > 1.0:
        return 1.0

    return value


class ReviewerAgent(BaseAgent):

    def generate_draft(
        self,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        prompt = PromptBuilder.build_review_prompt(
            task=task,
            skills=skills,
        )

        return self.llm.complete(
            prompt=prompt
        )

    def self_check(
        self,
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> ValidationReport:

        prompt = PromptBuilder.build_self_check_prompt(
            draft=draft,
            task=task,
            skills=skills,
        )

        response = self.llm.complete(
            prompt=prompt
        )

        parsed = self._parse_json(response)

        issues = [
            Issue(
                severity=_normalize_severity(
                    item.get("severity")
                ),
                message=item.get(
                    "message",
                    "",
                ),
                location=item.get(
                    "location",
                ),
            )
            for item in parsed.get(
                "issues",
                [],
            )
            if isinstance(
                item,
                dict,
            )
        ]

        return ValidationReport(
            is_valid=bool(
                parsed.get(
                    "is_valid",
                    False,
                )
            ),
            quality_score=_clamp_score(
                parsed.get(
                    "quality_score",
                    0.0,
                )
            ),
            clarity_score=_clamp_score(
                parsed.get(
                    "clarity_score",
                    0.0,
                )
            ),
            issues=issues,
            actions=[
                str(action)
                for action in parsed.get(
                    "actions",
                    [],
                )
            ],
        )

    def correct(
        self,
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        prompt = PromptBuilder.build_correction_prompt(
            draft=draft,
            report=report,
            task=task,
            skills=skills,
        )

        return self.llm.complete(
            prompt=prompt
        )

    @staticmethod
    def _parse_json(
        raw: str,
    ) -> dict:

        cleaned = raw.strip()

        if cleaned.startswith("```"):

            cleaned = cleaned.strip("`")

            lines = cleaned.splitlines()

            if (
                lines
                and lines[0]
                .lower()
                .startswith("json")
            ):
                lines = lines[1:]

            cleaned = (
                "\n".join(lines)
                .strip()
            )

        try:
            return json.loads(
                cleaned
            )

        except json.JSONDecodeError:
            return {}