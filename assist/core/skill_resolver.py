from pathlib import Path

import yaml

from assist.schemas.models import (
    Skill,
    SkillInputs,
    SkillOutputs,
    SkillOutputSections,
    SkillProcess,
    SkillVerifier,
)


class SkillNotFoundError(Exception):
    """Raised when a skill cannot be found."""


class SkillFormatError(Exception):
    """Raised when a skill file has malformed frontmatter or
    inconsistent v3.0 fields."""


# Coerenza task_type <-> outputs.format (v3.0)
_VALID_FORMAT_FOR_TASK_TYPE = {
    "prose": {"markdown"},
    "code": {"python"},
    "json": {"json"},
}


def _split_frontmatter(content: str) -> tuple[dict, str]:
    """Estrae il frontmatter YAML e il body markdown dal contenuto raw.

    Una skill ha frontmatter se inizia con '---' su una riga,
    seguito da YAML, seguito da '---' su una riga.

    Returns:
        Tuple (frontmatter_dict, body_markdown).
        Se la skill non ha frontmatter, ritorna ({}, content_intero).
    """
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines()

    # Cerca il '---' di chiusura (deve essere riga > 0)
    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break

    if end_index is None:
        # Inizia con --- ma non chiude: trattalo come content raw
        return {}, content

    frontmatter_lines = lines[1:end_index]
    body_lines = lines[end_index + 1:]

    frontmatter_text = "\n".join(frontmatter_lines)
    body_text = "\n".join(body_lines)

    try:
        frontmatter_dict = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        raise SkillFormatError(
            f"Malformed YAML in skill frontmatter: {e}"
        ) from e

    if not isinstance(frontmatter_dict, dict):
        raise SkillFormatError(
            f"Skill frontmatter must be a YAML mapping, "
            f"got {type(frontmatter_dict).__name__}"
        )

    return frontmatter_dict, body_text


def _parse_v3_fields(
    frontmatter: dict,
    skill_name: str,
) -> dict:
    """Parsa i campi v3.0 dal frontmatter.

    Validazioni applicate:
    - task_type obbligatorio
    - task_type valido (prose | code | json)
    - se outputs presente, format coerente con task_type
    - max_corrections in range [0, 3]
    - quality_threshold in range [0.0, 1.0]

    Returns:
        Dict con i campi v3.0 parsati (task_type, inputs, outputs,
        process, verifier). I valori sono modelli Pydantic o None.

    Raises:
        SkillFormatError: se la skill v3.0 e' malformata.
    """
    task_type = frontmatter.get("task_type")
    if task_type is None:
        raise SkillFormatError(
            f"Skill '{skill_name}' declares version 3.0 but is missing "
            f"required field 'task_type'"
        )

    if task_type not in {"prose", "code", "json"}:
        raise SkillFormatError(
            f"Skill '{skill_name}' has invalid task_type '{task_type}'. "
            f"Valid values: prose, code, json"
        )

    parsed: dict = {"task_type": task_type}

    # inputs (opzionale)
    raw_inputs = frontmatter.get("inputs")
    if raw_inputs is not None:
        try:
            parsed["inputs"] = SkillInputs(**raw_inputs)
        except Exception as e:
            raise SkillFormatError(
                f"Skill '{skill_name}' has invalid inputs: {e}"
            ) from e

    # outputs (opzionale, ma se presente va validato)
    raw_outputs = frontmatter.get("outputs")
    if raw_outputs is not None:
        try:
            sections_data = raw_outputs.get("sections")
            sections_model = None
            if sections_data is not None:
                sections_model = SkillOutputSections(**sections_data)

            outputs_model = SkillOutputs(
                format=raw_outputs.get("format"),
                sections=sections_model,
            )
            parsed["outputs"] = outputs_model
        except Exception as e:
            raise SkillFormatError(
                f"Skill '{skill_name}' has invalid outputs: {e}"
            ) from e

        # Coerenza task_type <-> outputs.format
        valid_formats = _VALID_FORMAT_FOR_TASK_TYPE[task_type]
        if outputs_model.format not in valid_formats:
            raise SkillFormatError(
                f"Skill '{skill_name}' has inconsistent task_type/outputs.format: "
                f"task_type='{task_type}' requires format in {valid_formats}, "
                f"got '{outputs_model.format}'"
            )

    # process (opzionale)
    raw_process = frontmatter.get("process")
    if raw_process is not None:
        try:
            parsed["process"] = SkillProcess(**raw_process)
        except Exception as e:
            raise SkillFormatError(
                f"Skill '{skill_name}' has invalid process config: {e}"
            ) from e

    # verifier (opzionale)
    raw_verifier = frontmatter.get("verifier")
    if raw_verifier is not None:
        try:
            parsed["verifier"] = SkillVerifier(**raw_verifier)
        except Exception as e:
            raise SkillFormatError(
                f"Skill '{skill_name}' has invalid verifier config: {e}"
            ) from e

    return parsed


class SkillResolver:
    def __init__(
        self,
        skills_path: str = "assist/skills",
    ) -> None:
        self.skills_path = Path(skills_path)

    def load(
        self,
        skill_names: list[str],
    ) -> list[Skill]:
        loaded_skills = []

        for skill_name in skill_names:
            skill_file = (
                self.skills_path
                / skill_name
                / "SKILL.md"
            )

            if not skill_file.exists():
                raise SkillNotFoundError(
                    f"Skill not found: {skill_name}"
                )

            content = skill_file.read_text(
                encoding="utf-8"
            )

            # Rimuovi UTF-8 BOM se presente. Su Windows, PowerShell
            # Set-Content -Encoding UTF8 aggiunge il BOM di default,
            # che impedisce a startswith("---") di riconoscere il
            # frontmatter e causa silent fallback a v2.5.
            content = content.lstrip("\ufeff")

            # Estrai frontmatter (parser non-fatale per skill senza FM)
            frontmatter, _body = _split_frontmatter(content)

            # Determina versione (default 2.5 per retrocompatibilita')
            version = str(frontmatter.get("version", "2.5"))

            # Costruzione campi base v2.5
            skill_kwargs: dict = {
                "name": skill_name,
                "content": content,
                "version": version,
            }

            # Se v3.0, parsa anche i campi runtime
            if version == "3.0":
                v3_fields = _parse_v3_fields(
                    frontmatter,
                    skill_name,
                )
                skill_kwargs.update(v3_fields)

            loaded_skills.append(
                Skill(**skill_kwargs)
            )

        return loaded_skills