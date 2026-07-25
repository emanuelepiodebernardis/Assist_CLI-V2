"""PromptBuilder — assembles prompts for the 21 (task x stage) combinations.

This file is a thin façade over `assist.core.prompt_templates.TEMPLATES`.
Each `build_*_prompt` method:
1. Reads variables from TaskInput / Skill / ValidationReport
2. Renders the corresponding template via str.format()

Public API preserved exactly: same method names, same signatures, same
returned strings (up to whitespace stripping). This file is the Step 1
output of Epic 1.2 — no behavioral change, only structural extraction.

Subsequent steps (2 -> 5) will fold these 21 thin methods into a single
declarative `build(task, skills, stage)` entrypoint.
"""

from __future__ import annotations

from assist.core.prompt_context_builder import (
    PromptContextBuilder,
)
from assist.core.prompt_templates import TEMPLATES
from assist.schemas.models import (
    Skill,
    TaskInput,
    ValidationReport,
)

# ────────────────────────────────────────────────────────────────────────
# Validation schema (private, shared by all self_check templates)
# ────────────────────────────────────────────────────────────────────────


_VALIDATION_JSON_SCHEMA: str = """
# FORMATO DI OUTPUT

Restituisci SOLO un JSON valido con questa struttura.

VINCOLI OBBLIGATORI:
- "severity" DEVE essere esattamente una di queste 4 stringhe:
  "critical", "high", "medium", "low"
  Non sono ammessi altri valori (no "minor", "info", "warning",
  "trivial", "blocker", ecc.).
- "is_valid" deve essere true o false (boolean, non stringa).
- "quality_score" e "clarity_score" devono essere numeri tra 0.0 e 1.0.
- "location" puo essere null oppure una stringa.

STRUTTURA:

{
  "is_valid": true,
  "quality_score": 0.0,
  "clarity_score": 0.0,
  "issues": [
    {
      "severity": "critical",
      "message": "string",
      "location": "string or null"
    }
  ],
  "actions": [
    "string"
  ]
}

Non aggiungere testo fuori dal JSON.
""".strip()


class PromptBuilder:

    # ────────────────────────────────────────────────────────────────
    # Private helpers (unchanged from the previous version)
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_skills_block(
        skills: list[Skill],
    ) -> str:

        return "\n\n".join(
            skill.content
            for skill in skills
        )

    @staticmethod
    def _build_context_block(
        task: TaskInput,
    ) -> str:

        context = (
            PromptContextBuilder()
            .aggregate(
                options=task.options,
                target_file=task.file_path,
            )
        )

        return (
            PromptContextBuilder()
            .render(context)
        )

    @staticmethod
    def _build_generation_request(
        task: TaskInput,
    ) -> str:

        candidates = [
            task.raw_input,
            task.options.get("prompt"),
            task.options.get("description"),
            task.options.get("specification"),
            task.options.get("goal"),
        ]

        for candidate in candidates:
            if (
                isinstance(candidate, str)
                and candidate.strip()
            ):
                return candidate.strip()

        target_name = (
            task.file_path
            or "nuovo modulo"
        )

        language = (
            task.language
            or "python"
        )

        return (
            f"Crea {target_name} in {language} seguendo "
            "il contesto strutturale e le skill fornite."
        )

    @staticmethod
    def _build_validation_json_schema() -> str:
        return _VALIDATION_JSON_SCHEMA

    @staticmethod
    def _build_impacted_files_block(
        task: TaskInput,
    ) -> str:
        """Costruisce la sezione FILE IMPATTATI con il contenuto
        di ogni file toccato dal diff.

        task.options["impacted_files_content"] e' un dict {path: content}
        popolato dall'orchestrator usando GitDiffExtractor + ProjectGraph.
        """

        impacted_files = (
            task.options.get(
                "impacted_files_content",
                {},
            )
        )

        if not impacted_files:
            return "(nessun file impattato disponibile)"

        sections = []

        for path, content in impacted_files.items():

            sections.append(
                f"## File: {path}\n\n"
                f"```python\n"
                f"{content}\n"
                f"```"
            )

        return "\n\n".join(sections)

    # ────────────────────────────────────────────────────────────────
    # REVIEW
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_review_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        if not task.raw_input:
            raise ValueError(
                "TaskInput.raw_input is empty. "
                "File content must be injected "
                "before prompt building."
            )

        return TEMPLATES["review"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
        ).strip()

    @staticmethod
    def build_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["review"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["review"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            report_json=report.model_dump_json(indent=2),
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # GENERATE
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_generate_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["generate"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            generation_request=PromptBuilder._build_generation_request(task),
            language=language,
        ).strip()

    @staticmethod
    def build_generate_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["generate"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            language=language,
            language_upper=language.upper(),
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_generate_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["generate"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            report_json=report.model_dump_json(indent=2),
            language=language,
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # REFACTOR
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_refactor_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        if not task.raw_input:
            raise ValueError(
                "TaskInput.raw_input is empty. "
                "File content must be injected "
                "before prompt building."
            )

        language = task.language or "python"

        return TEMPLATES["refactor"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            language=language,
        ).strip()

    @staticmethod
    def build_refactor_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["refactor"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            language=language,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_refactor_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["refactor"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            report_json=report.model_dump_json(indent=2),
            language=language,
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # EXPLAIN
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_explain_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        if not task.raw_input:
            raise ValueError(
                "TaskInput.raw_input is empty. "
                "File content must be injected "
                "before prompt building."
            )

        language = task.language or "python"
        depth = task.options.get("depth") or "brief"

        return TEMPLATES["explain"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            language=language,
            depth=depth,
        ).strip()

    @staticmethod
    def build_explain_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["explain"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_explain_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["explain"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            draft=draft,
            report_json=report.model_dump_json(indent=2),
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # TEST (pytest generation)
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_test_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        if not task.raw_input:
            raise ValueError(
                "TaskInput.raw_input is empty. "
                "File content must be injected "
                "before prompt building."
            )

        language = task.language or "python"

        return TEMPLATES["test"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            language=language,
        ).strip()

    @staticmethod
    def build_test_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["test"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            language=language,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_test_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        language = task.language or "python"

        return TEMPLATES["test"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            report_json=report.model_dump_json(indent=2),
            language=language,
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # DIFF (git diff review)
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_diff_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        if not task.raw_input:
            raise ValueError(
                "TaskInput.raw_input is empty. "
                "Git diff content must be injected "
                "before prompt building."
            )

        range_spec = task.options.get("range_spec", "HEAD")

        return TEMPLATES["diff"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            impacted_files_block=PromptBuilder._build_impacted_files_block(task),
            raw_input=task.raw_input,
            range_spec=range_spec,
        ).strip()

    @staticmethod
    def build_diff_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["diff"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_diff_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        return TEMPLATES["diff"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            raw_input=task.raw_input,
            draft=draft,
            report_json=report.model_dump_json(indent=2),
        ).strip()

    # ────────────────────────────────────────────────────────────────
    # REPO (repository overview)
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def build_repo_prompt(
        task: TaskInput,
        skills: list[Skill],
    ) -> str:
        """Costruisce il prompt per il task `repo`.

        Diversamente dagli altri task, repo non ha task.raw_input
        (non c'e' un singolo file da analizzare). Tutto il segnale
        per l'overview deriva dal context strutturale aggregato a
        livello di repository, popolato dall'orchestrator.

        L'agente legge:
        - task.repo_path: identifica il repository analizzato
        - context aggregato: project_size, health_score, god_classes,
          long_methods, complexity_warnings, risks, ecc.
        """

        repo_path = task.repo_path or "."

        return TEMPLATES["repo"]["draft"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            repo_path=repo_path,
        ).strip()

    @staticmethod
    def build_repo_self_check_prompt(
        draft: str,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        repo_path = task.repo_path or "."

        return TEMPLATES["repo"]["self_check"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            repo_path=repo_path,
            draft=draft,
            validation_schema=_VALIDATION_JSON_SCHEMA,
        ).strip()

    @staticmethod
    def build_repo_correction_prompt(
        draft: str,
        report: ValidationReport,
        task: TaskInput,
        skills: list[Skill],
    ) -> str:

        repo_path = task.repo_path or "."

        return TEMPLATES["repo"]["correct"].format(
            skills_block=PromptBuilder._build_skills_block(skills),
            rendered_context=PromptBuilder._build_context_block(task),
            repo_path=repo_path,
            draft=draft,
            report_json=report.model_dump_json(indent=2),
        ).strip()