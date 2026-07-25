import pytest

from assist.core.skill_resolver import (
    SkillFormatError,
    SkillNotFoundError,
    SkillResolver,
)


def test_load_existing_skill():
    resolver = SkillResolver()

    skills = resolver.load(
        ["project_rules"]
    )

    assert len(skills) == 1
    assert skills[0].name == "project_rules"


def test_missing_skill_raises():
    resolver = SkillResolver()

    with pytest.raises(SkillNotFoundError):
        resolver.load(
            ["missing_skill"]
        )


# Helper per creare skill fittizie nei test


def _write_skill(
    tmp_path,
    name: str,
    content: str,
) -> SkillResolver:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        content,
        encoding="utf-8",
    )
    return SkillResolver(
        skills_path=str(tmp_path),
    )


# Test v3.0 SkillResolver


def test_load_v25_skill_unchanged(tmp_path):
    """Una skill v2.5 esistente carica con campi v3.0 a None."""
    content = """---
name: test_skill
version: 2.5
applies_to: [review]
---

# test_skill v2.5

Body markdown content.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    skills = resolver.load(["test_skill"])

    assert len(skills) == 1
    skill = skills[0]
    assert skill.name == "test_skill"
    assert skill.version == "2.5"
    assert skill.task_type is None
    assert skill.inputs is None
    assert skill.outputs is None
    assert skill.process is None
    assert skill.verifier is None


def test_load_v30_skill_complete(tmp_path):
    """Una skill v3.0 con tutti i campi carica con campi popolati."""
    content = """---
name: test_skill
version: 3.0
applies_to: [review]
task_type: prose
inputs:
  required:
    - raw_input
  optional:
    - options
outputs:
  format: markdown
  sections:
    required:
      - "## Sommario"
    optional:
      - "## Suggerimenti"
process:
  max_corrections: 1
  quality_threshold: 0.75
verifier:
  syntax: noop
  format: section_headers
  coherence: rubric
---

# test_skill v3.0

Body markdown.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    skills = resolver.load(["test_skill"])

    assert len(skills) == 1
    skill = skills[0]
    assert skill.version == "3.0"
    assert skill.task_type == "prose"

    assert skill.inputs is not None
    assert skill.inputs.required == ["raw_input"]
    assert skill.inputs.optional == ["options"]

    assert skill.outputs is not None
    assert skill.outputs.format == "markdown"
    assert skill.outputs.sections is not None
    assert skill.outputs.sections.required == ["## Sommario"]

    assert skill.process is not None
    assert skill.process.max_corrections == 1
    assert skill.process.quality_threshold == 0.75

    assert skill.verifier is not None
    assert skill.verifier.syntax == "noop"
    assert skill.verifier.format == "section_headers"
    assert skill.verifier.coherence == "rubric"


def test_load_v30_skill_missing_task_type(tmp_path):
    """Una skill v3.0 senza task_type produce errore esplicito."""
    content = """---
name: test_skill
version: 3.0
---

Body.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    with pytest.raises(SkillFormatError, match="task_type"):
        resolver.load(["test_skill"])


def test_load_v30_skill_invalid_task_type(tmp_path):
    """Una skill v3.0 con task_type non valido produce errore."""
    content = """---
name: test_skill
version: 3.0
task_type: nonsense
---

Body.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    with pytest.raises(SkillFormatError, match="invalid task_type"):
        resolver.load(["test_skill"])


def test_load_v30_skill_inconsistent_format(tmp_path):
    """task_type=prose con format=python -> errore di coerenza."""
    content = """---
name: test_skill
version: 3.0
task_type: prose
outputs:
  format: python
---

Body.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    with pytest.raises(SkillFormatError, match="inconsistent"):
        resolver.load(["test_skill"])


def test_load_malformed_yaml(tmp_path):
    """YAML malformato nel frontmatter produce errore chiaro."""
    content = """---
name: test_skill
version: 3.0
inputs:
  required:
    - raw_input
   bad_indent: oops
---

Body.
"""
    resolver = _write_skill(tmp_path, "test_skill", content)

    with pytest.raises(SkillFormatError, match="Malformed YAML"):
        resolver.load(["test_skill"])


def test_load_skill_no_frontmatter(tmp_path):
    """Skill senza frontmatter --- e' trattata come v2.5 con content raw."""
    content = "# Just a markdown file, no frontmatter\n\nSome content."
    resolver = _write_skill(tmp_path, "test_skill", content)

    skills = resolver.load(["test_skill"])

    assert len(skills) == 1
    skill = skills[0]
    assert skill.version == "2.5"
    assert skill.task_type is None
    assert skill.content == content


def test_load_v30_skill_with_utf8_bom(tmp_path):
    """Skill v3.0 con UTF-8 BOM in testa al file carica correttamente.

    Regressione: PowerShell Set-Content -Encoding UTF8 su Windows
    aggiunge il BOM di default. Senza la pulizia, il frontmatter
    non veniva riconosciuto e la skill veniva trattata come v2.5
    fallback con i campi v3.0 silenziosamente ignorati.
    """
    content = """---
name: test_skill
version: 3.0
task_type: code
inputs:
  required:
    - raw_input
outputs:
  format: python
verifier:
  syntax: ast
  format: noop
  coherence: rubric
---

# test_skill v3.0

Body.
"""

    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"

    # Scrivi il file CON il BOM UTF-8 in testa
    skill_file.write_bytes(
        b"\xef\xbb\xbf" + content.encode("utf-8")
    )

    resolver = SkillResolver(
        skills_path=str(tmp_path),
    )
    skills = resolver.load(["test_skill"])

    assert len(skills) == 1
    skill = skills[0]
    assert skill.version == "3.0"
    assert skill.task_type == "code"
    assert skill.outputs is not None
    assert skill.outputs.format == "python"
    assert skill.verifier is not None
    assert skill.verifier.syntax == "ast"