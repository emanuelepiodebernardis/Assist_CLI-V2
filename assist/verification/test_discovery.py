"""Auto-discovery del file di test associato a un modulo target.

Cerca il file di test seguendo le convenzioni pytest piu' comuni:
prima nella stessa directory del modulo, poi risalendo verso la
project root. Nessuna esecuzione di codice: solo controlli sul
filesystem.
"""

from pathlib import Path

MAX_LEVELS = 5

PROJECT_ROOT_MARKERS = ("pyproject.toml", "setup.py", ".git")

TEST_SUBDIRS = ("tests", "tests/unit", "test")


class TestDiscovery:
    """Trova il file di test per un modulo Python target."""

    __test__ = False  # evita la collection di pytest

    def find_tests(self, target_file: str) -> str | None:
        """Cerca il file di test per `target_file`.

        Ordine di ricerca:
        1. `test_<stem>.py` e `<stem>_test.py` nella stessa directory
           del target;
        2. `tests/test_<stem>.py`, `tests/unit/test_<stem>.py` e
           `test/test_<stem>.py` risalendo dalla directory del target
           fino alla project root (directory contenente
           `pyproject.toml`, `setup.py` o `.git`), fermandosi
           comunque dopo al massimo `MAX_LEVELS` livelli.

        Ritorna il path assoluto del file di test come stringa, o
        `None` se nessun file di test viene trovato.
        """
        target = Path(target_file).resolve()
        stem = target.stem
        directory = target.parent

        same_dir_candidates = (
            directory / f"test_{stem}.py",
            directory / f"{stem}_test.py",
        )

        for candidate in same_dir_candidates:
            if candidate.is_file():
                return str(candidate)

        return self._search_upwards(directory, stem)

    def _search_upwards(self, start: Path, stem: str) -> str | None:
        """Risale da `start` cercando `test_<stem>.py` nelle
        sottodirectory di test convenzionali, fino alla project root
        (se individuabile) o al limite di `MAX_LEVELS` livelli."""
        project_root = self._find_project_root(start)

        current = start
        levels = 0

        while levels <= MAX_LEVELS:
            for subdir in TEST_SUBDIRS:
                candidate = current / subdir / f"test_{stem}.py"
                if candidate.is_file():
                    return str(candidate)

            if project_root is not None and current == project_root:
                break

            if current.parent == current:
                break

            current = current.parent
            levels += 1

        return None

    def _find_project_root(self, start: Path) -> Path | None:
        """Risale da `start` cercando un marker di project root
        (`pyproject.toml`, `setup.py` o `.git`), fino a `MAX_LEVELS`
        livelli. Ritorna `None` se nessun marker viene trovato entro
        il limite."""
        current = start
        levels = 0

        while levels <= MAX_LEVELS:
            for marker in PROJECT_ROOT_MARKERS:
                if (current / marker).exists():
                    return current

            if current.parent == current:
                break

            current = current.parent
            levels += 1

        return None
