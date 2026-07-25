from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assist.core.git_diff_extractor import (
    GitDiffExtractor,
    GitDiffExtractionError,
)


# =====================================================================
# Fixture: repo git temporaneo
#
# Crea un repo git inizializzato in tmp_path con identita' git
# locale fittizia (necessaria per fare commit anche in CI).
#
# La fixture restituisce il path della repo. I test la usano
# per scrivere file, fare commit, e poi estrarre diff.
# =====================================================================


@pytest.fixture
def git_repo(
    tmp_path: Path,
) -> Path:
    """Crea un repo git temporaneo con identita' configurata."""

    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )

    # Identita' locale necessaria per commit in CI
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "test@example.com",
        ],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "git",
            "config",
            "user.name",
            "Test User",
        ],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )

    return tmp_path


def _git_commit_all(
    repo_path: Path,
    message: str,
) -> None:
    """Helper: aggiunge tutti i file modificati e fa un commit."""

    subprocess.run(
        ["git", "add", "."],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            message,
        ],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


# =====================================================================
# Test
# =====================================================================


def test_extract_simple_diff(
    git_repo: Path,
):
    """Modifica un file e verifica che il diff abbia counts corretti."""

    # Setup: crea un file, commit iniziale
    target = git_repo / "module.py"

    target.write_text(
        "def foo():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    _git_commit_all(
        git_repo,
        "initial commit",
    )

    # Modifica il file
    target.write_text(
        "def foo():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    # Estrai il diff
    extractor = GitDiffExtractor(
        repo_path=git_repo
    )

    diff = extractor.extract(
        "HEAD"
    )

    # Verifiche aggregati
    assert diff.range_spec == "HEAD"
    assert diff.files_changed == 1
    assert diff.total_additions == 1
    assert diff.total_deletions == 1

    # Verifiche del singolo file
    assert len(diff.files) == 1

    file_diff = diff.files[0]

    assert file_diff.path == "module.py"
    assert file_diff.additions == 1
    assert file_diff.deletions == 1

    # Il raw_diff deve contenere il marker della modifica
    assert (
        "+    return 2"
        in diff.raw_diff
    )

    assert (
        "-    return 1"
        in diff.raw_diff
    )

    # Gli hunks del file devono contenere lo stesso
    assert (
        "+    return 2"
        in file_diff.hunks
    )


def test_extract_empty_diff(
    git_repo: Path,
):
    """Senza modifiche, files deve essere vuoto."""

    # Setup: crea un file e commit
    target = git_repo / "module.py"

    target.write_text(
        "def foo():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    _git_commit_all(
        git_repo,
        "initial commit",
    )

    # Nessuna modifica
    extractor = GitDiffExtractor(
        repo_path=git_repo
    )

    diff = extractor.extract(
        "HEAD"
    )

    # Verifiche
    assert diff.files_changed == 0
    assert diff.total_additions == 0
    assert diff.total_deletions == 0
    assert diff.files == []
    assert diff.raw_diff == ""


def test_extract_handles_invalid_range(
    git_repo: Path,
):
    """Un range invalido deve sollevare GitDiffExtractionError."""

    # Setup minimo: serve almeno un commit perche' HEAD esista
    target = git_repo / "module.py"

    target.write_text(
        "x = 1\n",
        encoding="utf-8",
    )

    _git_commit_all(
        git_repo,
        "initial commit",
    )

    # Range invalido: in un repo con un solo commit, HEAD~999 non esiste
    extractor = GitDiffExtractor(
        repo_path=git_repo
    )

    with pytest.raises(
        GitDiffExtractionError
    ):
        extractor.extract(
            "HEAD~999"
        )


def test_extract_multiple_files(
    git_repo: Path,
):
    """Diff su piu' file: ogni file appare in files con i suoi counts."""

    # Setup: due file, commit iniziale
    file_a = git_repo / "module_a.py"

    file_a.write_text(
        "def a():\n"
        "    pass\n",
        encoding="utf-8",
    )

    file_b = git_repo / "module_b.py"

    file_b.write_text(
        "def b():\n"
        "    pass\n",
        encoding="utf-8",
    )

    _git_commit_all(
        git_repo,
        "initial commit",
    )

    # Modifica entrambi i file
    file_a.write_text(
        "def a() -> int:\n"
        "    return 1\n"
        "\n"
        "def a_new() -> int:\n"
        "    return 2\n",
        encoding="utf-8",
    )

    file_b.write_text(
        "def b() -> int:\n"
        "    return 0\n",
        encoding="utf-8",
    )

    # Estrai il diff
    extractor = GitDiffExtractor(
        repo_path=git_repo
    )

    diff = extractor.extract(
        "HEAD"
    )

    # Aggregati
    assert diff.files_changed == 2

    paths = sorted(
        file_diff.path
        for file_diff in diff.files
    )

    assert paths == [
        "module_a.py",
        "module_b.py",
    ]

    # Verifica che i counts per file siano coerenti
    by_path = {
        file_diff.path: file_diff
        for file_diff in diff.files
    }

    # module_a: aggiunte 4 righe nuove (def a_new + return 2 + due
    # modifiche alla riga di a()), rimosse 2 righe vecchie
    assert by_path["module_a.py"].additions > 0
    assert by_path["module_a.py"].deletions > 0

    # module_b: aggiunte 2 righe, rimosse 2
    assert by_path["module_b.py"].additions > 0
    assert by_path["module_b.py"].deletions > 0

    # Gli hunks di ogni file devono contenere solo le modifiche
    # di quel file, non dell'altro
    assert (
        "def a_new"
        in by_path["module_a.py"].hunks
    )

    assert (
        "def a_new"
        not in by_path["module_b.py"].hunks
    )