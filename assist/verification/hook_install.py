"""Installazione degli hook che collegano la verifica alla scrittura.

Fornisce due meccanismi per agganciare `assist verify` al momento in
cui il codice viene scritto, prima che possa propagarsi:

- un hook Git ``pre-commit`` (universale, funziona con qualunque
  editor/IDE, incluso Cursor);
- un hook ``PostToolUse`` per Claude Code, che verifica il file subito
  dopo che uno strumento ``Edit``/``Write`` lo ha modificato.

Le funzioni di questo modulo scrivono i file di configurazione sul
disco senza eseguire nulla: l'esecuzione effettiva avviene poi da Git
o da Claude Code.
"""

import json
import stat
from pathlib import Path
from typing import Any

_HOOK_MARKER = "# assist-cli hook"

PRE_COMMIT_SCRIPT: str = f"""#!/bin/sh
{_HOOK_MARKER}
# Hook pre-commit generato da Assist CLI.
#
# Verifica ogni file Python staged con `assist verify` prima di
# permettere il commit. Se un file fallisce la verifica (exit 1),
# il commit viene bloccato.

# Raccoglie i file .py aggiunti/modificati/rinominati che sono in
# staging (indice Git), non l'intero albero di lavoro.
files=$(git diff --cached --name-only --diff-filter=ACM -- '*.py')

# Nessun file Python staged: non c'e' nulla da verificare.
if [ -z "$files" ]; then
    exit 0
fi

# Verifica ogni file uno per uno: al primo fallimento il commit
# viene interrotto (exit 1 propagato).
for file in $files; do
    python -m assist.cli.main verify "$file" || exit 1
done

exit 0
"""

CLAUDE_CODE_HOOK_SETTINGS: dict[str, Any] = {
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            'python -m assist.cli.main verify '
                            '"$CLAUDE_FILE_PATHS" --format markdown'
                        ),
                    }
                ],
            }
        ]
    }
}


def _has_assist_marker(script_path: Path) -> bool:
    """True se ``script_path`` contiene il marker degli hook Assist."""

    try:
        content = script_path.read_text(encoding="utf-8")
    except OSError:
        return False

    return _HOOK_MARKER in content


def install_pre_commit(repo_dir: str | Path = ".") -> Path:
    """Installa l'hook Git ``pre-commit`` di Assist CLI nel repository.

    Scrive ``PRE_COMMIT_SCRIPT`` in ``<repo_dir>/.git/hooks/pre-commit``
    e lo rende eseguibile. Se il repository ha gia' un hook
    ``pre-commit`` non generato da Assist CLI (riconosciuto dal marker
    ``# assist-cli hook``), la funzione non lo sovrascrive e solleva
    ``ValueError`` suggerendo di integrarlo manualmente.

    Solleva ``ValueError`` se ``repo_dir`` non e' un repository Git
    (assenza della directory ``.git``).

    Ritorna il path del file dell'hook scritto.
    """

    repo_path = Path(repo_dir)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise ValueError(
            f"'{repo_path}' non è un repository Git: directory "
            f"'{git_dir}' non trovata."
        )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and not _has_assist_marker(hook_path):
        raise ValueError(
            f"'{hook_path}' esiste già e non è stato creato da Assist "
            "CLI (manca il marker '# assist-cli hook'). Integra a "
            "mano la verifica nel tuo hook esistente invece di "
            "sovrascriverlo."
        )

    hook_path.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8")

    current_mode = hook_path.stat().st_mode
    hook_path.chmod(
        current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    return hook_path


def _hook_already_present(
    post_tool_use: list[dict[str, Any]], command: str
) -> bool:
    """True se un hook con lo stesso comando è già registrato.

    Cerca ``command`` tra tutte le voci ``hooks`` di tutti i matcher
    già presenti in ``post_tool_use``, per evitare duplicati.
    """

    for entry in post_tool_use:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True

    return False


def _merge_claude_code_settings(
    existing: dict[str, Any],
) -> dict[str, Any]:
    """Unisce ``CLAUDE_CODE_HOOK_SETTINGS`` dentro ``existing``.

    Conserva tutte le chiavi già presenti in ``existing`` (comprese
    quelle non legate agli hook, es. ``"model"``) ed estende
    ``hooks.PostToolUse`` senza duplicare hook con lo stesso comando.
    """

    merged = dict(existing)
    hooks_section = dict(merged.get("hooks", {}))
    post_tool_use = list(hooks_section.get("PostToolUse", []))

    new_entry = CLAUDE_CODE_HOOK_SETTINGS["hooks"]["PostToolUse"][0]
    new_command = new_entry["hooks"][0]["command"]

    if not _hook_already_present(post_tool_use, new_command):
        post_tool_use.append(json.loads(json.dumps(new_entry)))

    hooks_section["PostToolUse"] = post_tool_use
    merged["hooks"] = hooks_section

    return merged


def install_claude_code_hook(repo_dir: str | Path = ".") -> Path:
    """Installa l'hook ``PostToolUse`` di Claude Code nel repository.

    Crea (o aggiorna) ``<repo_dir>/.claude/settings.json`` con la
    configurazione ``CLAUDE_CODE_HOOK_SETTINGS``. Se il file esiste
    già, fa il merge preservando le chiavi esistenti (incluse quelle
    non legate agli hook) ed estendendo ``hooks.PostToolUse`` senza
    duplicare un hook con lo stesso comando già registrato.

    Ritorna il path del file scritto.
    """

    claude_dir = Path(repo_dir) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"

    if settings_path.exists():
        existing_text = settings_path.read_text(encoding="utf-8")
        existing = json.loads(existing_text) if existing_text.strip() else {}
        merged = _merge_claude_code_settings(existing)
    else:
        merged = json.loads(json.dumps(CLAUDE_CODE_HOOK_SETTINGS))

    settings_path.write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8"
    )

    return settings_path


def render_instructions() -> str:
    """Ritorna una breve spiegazione in italiano dei due hook.

    Descrive l'hook Git ``pre-commit`` e l'hook ``PostToolUse`` di
    Claude Code, e come installarli tramite il comando CLI dedicato.
    """

    return (
        "Assist CLI può agganciare la verifica automatica al momento "
        "in cui il codice viene scritto, tramite due meccanismi "
        "complementari:\n\n"
        "1. Hook Git 'pre-commit': blocca il commit se un file "
        "Python staged fallisce 'assist verify'. Funziona con "
        "qualunque editor o IDE (incluso Cursor), perché agisce a "
        "livello di Git e non di editor.\n"
        "2. Hook 'PostToolUse' di Claude Code: verifica un file "
        "subito dopo che uno strumento Edit o Write lo ha "
        "modificato, mostrando il report in formato markdown.\n\n"
        "Per installarli entrambi:\n\n"
        "    assist install-hooks --pre-commit --claude-code\n"
    )
