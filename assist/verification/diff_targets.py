"""Estrazione dei target di verifica da un diff git.

Converte gli hunk di `git diff` nelle righe modificate del file
nuovo, per limitare mutation testing e verifica al codice toccato
(mutazione guidata dal diff, Fase 1 della roadmap).
"""

import re

from assist.schemas.models import GitDiff

_HUNK_HEADER = re.compile(
    r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@",
    re.MULTILINE,
)


def changed_lines_from_hunks(hunks: str) -> set[int]:
    """Ritorna l'insieme delle righe (lato file nuovo) coperte
    dagli hunk di un diff unificato."""

    lines: set[int] = set()

    for match in _HUNK_HEADER.finditer(hunks):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) else 1
        lines.update(range(start, start + count))

    return lines


def python_targets_from_diff(
    diff: GitDiff,
) -> dict[str, set[int]]:
    """Ritorna {path_file_python: righe_modificate} per i file
    Python toccati dal diff."""

    targets: dict[str, set[int]] = {}

    for file_diff in diff.files:
        if not file_diff.path.endswith(".py"):
            continue

        lines = changed_lines_from_hunks(file_diff.hunks)

        if lines:
            targets[file_diff.path] = lines

    return targets
