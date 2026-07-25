"""Configurazione di verifica per-repository (file `.assist.yaml`).

Permette di sovrascrivere, a livello di singolo repository, alcuni
parametri della pipeline di verifica definiti globalmente in
``assist/core/config.py`` (sezione ``VerifyConfig``), senza dover
toccare la configurazione globale dell'utente.
"""

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

_CONFIG_FILENAME = ".assist.yaml"
_PROJECT_MARKERS = ("pyproject.toml", "setup.py", ".git")
_MAX_LEVELS = 5


class RepoVerifyConfig(BaseModel):
    """Override per-repo dei parametri della pipeline di verifica.

    Tutti i campi numerici/booleani sono opzionali: se ``None`` non
    sovrascrivono il default globale (vedi ``merged_with``).
    """

    mutation_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    sandbox_timeout_seconds: int | None = Field(default=None, ge=1)
    max_mutants: int | None = Field(default=None, ge=1)
    generate_boundary_tests: bool | None = None
    max_fix_iterations: int | None = Field(default=None, ge=0)
    exclude: list[str] = Field(default_factory=list)

    def merged_with(
        self,
        *,
        mutation_threshold: float,
        sandbox_timeout_seconds: int,
        max_mutants: int,
        generate_boundary_tests: bool,
        max_fix_iterations: int,
    ) -> dict[str, Any]:
        """Unisce l'override di repo con i default globali passati.

        Per ogni parametro: se il valore in questa istanza non è
        ``None`` prevale quello del repo, altrimenti si usa il
        default globale ricevuto come argomento.
        """

        return {
            "mutation_threshold": (
                self.mutation_threshold
                if self.mutation_threshold is not None
                else mutation_threshold
            ),
            "sandbox_timeout_seconds": (
                self.sandbox_timeout_seconds
                if self.sandbox_timeout_seconds is not None
                else sandbox_timeout_seconds
            ),
            "max_mutants": (
                self.max_mutants
                if self.max_mutants is not None
                else max_mutants
            ),
            "generate_boundary_tests": (
                self.generate_boundary_tests
                if self.generate_boundary_tests is not None
                else generate_boundary_tests
            ),
            "max_fix_iterations": (
                self.max_fix_iterations
                if self.max_fix_iterations is not None
                else max_fix_iterations
            ),
        }


def _is_project_root(directory: Path) -> bool:
    """True se ``directory`` contiene uno dei marker di project root."""

    return any((directory / marker).exists() for marker in _PROJECT_MARKERS)


def _find_config_file(start_dir: str | Path) -> Path | None:
    """Cerca ``.assist.yaml`` risalendo da ``start_dir``.

    La risalita si ferma alla project root (individuata da uno dei
    marker in ``_PROJECT_MARKERS``) o dopo ``_MAX_LEVELS`` livelli,
    quello che avviene prima. Ritorna ``None`` se non trovato.
    """

    current = Path(start_dir).resolve()

    for _ in range(_MAX_LEVELS + 1):
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate

        if _is_project_root(current):
            break

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def load_repo_config(start_dir: str | Path = ".") -> RepoVerifyConfig:
    """Carica la configurazione di repo da ``.assist.yaml``.

    Risale l'albero delle directory partendo da ``start_dir`` fino a
    trovare il file, incontrare una project root (marker: pyproject.toml,
    setup.py, .git) o superare ``_MAX_LEVELS`` livelli. Se il file non
    viene trovato ritorna una ``RepoVerifyConfig`` con tutti i default.

    Solleva ``ValueError`` se il file esiste ma è YAML malformato o
    contiene campi non validi, includendo nel messaggio il path del
    file incriminato.
    """

    config_path = _find_config_file(start_dir)
    if config_path is None:
        return RepoVerifyConfig()

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        raise ValueError(
            f"YAML malformato in {config_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Contenuto non valido in {config_path}: atteso un "
            "mapping YAML."
        )

    try:
        return RepoVerifyConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Configurazione non valida in {config_path}: {exc}"
        ) from exc


def is_excluded(
    file_path: str | Path,
    config: RepoVerifyConfig,
    base_dir: str | Path = ".",
) -> bool:
    """True se ``file_path`` matcha uno dei pattern glob di ``exclude``.

    Il confronto è fatto sia sul path relativo a ``base_dir`` (con
    separatori normalizzati a ``/``) sia sul solo nome del file, in
    modo che pattern come ``"migrations/*.py"`` o ``"*_test.py"``
    funzionino entrambi.
    """

    if not config.exclude:
        return False

    path = Path(file_path)
    try:
        relative = path.resolve().relative_to(Path(base_dir).resolve())
    except ValueError:
        relative = path

    relative_str = relative.as_posix()
    name = path.name

    return any(
        fnmatch(relative_str, pattern) or fnmatch(name, pattern)
        for pattern in config.exclude
    )
