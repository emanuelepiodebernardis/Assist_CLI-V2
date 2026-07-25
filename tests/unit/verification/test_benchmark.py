"""Test di validazione strutturale del corpus del benchmark.

Non esegue l'intero benchmark (troppo lento: richiederebbe mutation
testing in sandbox per ogni caso). Verifica solo che:

- ogni directory del corpus contenga i tre file richiesti;
- ogni ``caso.yaml`` sia valido (campi richiesti presenti e
  categoria tra quelle coperte dai mutatori del motore);
- per almeno un caso il file di test del corpus passi davvero contro
  il codice buggato (il "test-bugia" che non rileva il bug).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from benchmark.run_benchmark import _CATEGORIE_VALIDE, CORPUS_DIR

_CAMPI_RICHIESTI = ("name", "bug_description", "bug_line", "categoria")


def _corpus_dirs() -> list[Path]:
    """Ritorna le directory dei casi del corpus, ordinate per nome."""
    return sorted(p for p in CORPUS_DIR.iterdir() if p.is_dir())


def test_corpus_ha_almeno_otto_casi() -> None:
    """Il corpus deve contenere almeno gli 8 casi richiesti."""
    assert len(_corpus_dirs()) >= 8


@pytest.mark.parametrize("case_dir", _corpus_dirs(), ids=lambda p: p.name)
def test_ogni_caso_ha_i_tre_file_richiesti(case_dir: Path) -> None:
    """Ogni caso deve avere target.py, test_target.py e caso.yaml."""
    assert (case_dir / "target.py").is_file()
    assert (case_dir / "test_target.py").is_file()
    assert (case_dir / "caso.yaml").is_file()


@pytest.mark.parametrize("case_dir", _corpus_dirs(), ids=lambda p: p.name)
def test_caso_yaml_valido(case_dir: Path) -> None:
    """Ogni caso.yaml deve avere i campi richiesti e una categoria nota."""
    data = yaml.safe_load((case_dir / "caso.yaml").read_text(encoding="utf-8"))

    assert isinstance(data, dict)

    for campo in _CAMPI_RICHIESTI:
        assert campo in data, f"{case_dir.name}: manca il campo {campo!r}"

    assert isinstance(data["name"], str) and data["name"]
    assert isinstance(data["bug_description"], str) and data["bug_description"]
    assert isinstance(data["bug_line"], int)
    assert data["bug_line"] > 0
    assert data["categoria"] in _CATEGORIE_VALIDE, (
        f"{case_dir.name}: categoria non coperta dai mutatori: "
        f"{data['categoria']!r}"
    )


def test_almeno_un_caso_pytest_passa_col_codice_buggato(
    tmp_path: Path,
) -> None:
    """Verifica che il test-bugia di almeno un caso passi davvero.

    Copia target.py e test_target.py di ciascun caso (in ordine) in
    una directory temporanea e ci esegue pytest: si ferma al primo
    caso per cui il test suite passa (exit code 0) col codice
    buggato, che e' esattamente il comportamento atteso dal corpus.
    """
    almeno_uno_passato = False

    for case_dir in _corpus_dirs():
        case_tmp = tmp_path / case_dir.name
        case_tmp.mkdir()

        shutil.copy(case_dir / "target.py", case_tmp / "target.py")
        shutil.copy(case_dir / "test_target.py", case_tmp / "test_target.py")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "test_target.py"],
            cwd=case_tmp,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            almeno_uno_passato = True
            break

    assert almeno_uno_passato, "Nessun caso del corpus passa col codice buggato"
