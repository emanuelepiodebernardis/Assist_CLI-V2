# Esempio: funzione ben strutturata

"""
Questo esempio mostra lo standard atteso per una funzione Python
generata da Assist CLI. Usalo come riferimento per calibrare
struttura, docstring, type hints e gestione errori.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_FILE_SIZE_BYTES: int = 1_000_000  # 1 MB


def load_skill(skill_path: Path) -> dict[str, Any]:
    """Carica e deserializza una skill dal filesystem.

    Legge il file SKILL.md, estrae il frontmatter YAML e restituisce
    i metadati della skill come dizionario validato.

    Args:
        skill_path: Percorso assoluto o relativo al file SKILL.md.
                    Il file deve esistere ed essere leggibile.

    Returns:
        Dict con i metadati della skill. Contiene sempre le chiavi
        'name', 'version', 'applies_to'. Può contenere 'description',
        'load_examples', 'load_templates'.

    Raises:
        FileNotFoundError: Se skill_path non esiste.
        ValueError: Se il file è troppo grande (> 1 MB) o il
                    frontmatter è assente o malformato.
        PermissionError: Se il file non è leggibile.

    Example:
        >>> path = Path("skills/python_generation/SKILL.md")
        >>> skill = load_skill(path)
        >>> skill["name"]
        'python_generation'
    """
    if not skill_path.exists():
        raise FileNotFoundError(
            f"Skill non trovata: {skill_path}. "
            f"Verifica che il percorso sia corretto."
        )

    file_size = skill_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File skill troppo grande: {file_size} byte "
            f"(limite: {MAX_FILE_SIZE_BYTES}). "
            f"Verifica che il file non sia corrotto."
        )

    content = skill_path.read_text(encoding="utf-8")
    return _parse_frontmatter(content, skill_path)


def _parse_frontmatter(content: str, source: Path) -> dict[str, Any]:
    """Estrae il frontmatter YAML dal contenuto di un SKILL.md.

    Args:
        content: Contenuto completo del file.
        source: Percorso del file, usato nei messaggi di errore.

    Returns:
        Dict con i metadati estratti dal frontmatter.

    Raises:
        ValueError: Se il frontmatter è assente, malformato o
                    mancano chiavi obbligatorie.
    """
    import yaml  # import locale: yaml è usato solo qui

    if not content.startswith("---"):
        raise ValueError(
            f"Frontmatter YAML assente in {source}. "
            f"Il file deve iniziare con '---'."
        )

    parts = content.split("---", maxsplit=2)
    if len(parts) < 3:
        raise ValueError(
            f"Frontmatter YAML malformato in {source}. "
            f"Assicurati di chiudere il blocco con '---'."
        )

    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        raise ValueError(f"Errore nel parsing del frontmatter di {source}: {e}") from e

    _validate_required_keys(metadata, source)
    return metadata


def _validate_required_keys(metadata: dict[str, Any], source: Path) -> None:
    """Verifica che le chiavi obbligatorie siano presenti.

    Args:
        metadata: Dict estratto dal frontmatter.
        source: Percorso del file, usato nei messaggi di errore.

    Raises:
        ValueError: Se una o più chiavi obbligatorie sono assenti.
    """
    required = {"name", "version", "applies_to"}
    missing = required - set(metadata.keys())
    if missing:
        raise ValueError(
            f"Chiavi obbligatorie assenti nel frontmatter di {source}: "
            f"{', '.join(sorted(missing))}"
        )
