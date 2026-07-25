"""Mappa di copertura per-test per il mutation testing (Fase A).

Per ogni mutante generato dal `MutationEngine` serve sapere quali test
"vedono" la riga mutata, cosi' da eseguire solo quel sottoinsieme
invece dell'intera suite (riduzione attesa 50-80% del tempo).

`build_coverage_map` esegue la suite UNA sola volta con `coverage` in
modalita' a contesti dinamici per-test (`--cov-context=test`) e
costruisce, dal report JSON prodotto, il dizionario
{numero di riga -> insieme di test node id}.

Nota tecnica: `SandboxRunner.run_pytest` cancella la workdir nel
blocco `finally` e non espone un modo generico per recuperare file
arbitrari prodotti durante il run (solo il report JUnit XML, via
`junit_xml_out`). Per il report JSON di coverage si usa quindi
`SandboxRunner.run_script` con un piccolo driver che invoca
`pytest.main(...)` e poi stampa il contenuto del file JSON di
coverage sullo stdout, delimitato da due marker univoci: lo stdout
del `SandboxResult` sopravvive alla pulizia della workdir, a
differenza del file su disco. Questo approccio e' stato verificato
empiricamente (run manuali in fase di sviluppo, vedi note nel PR)
prima di essere adottato: senza un `.coveragerc` con
`[json] show_contexts = True` il report JSON non contiene affatto la
chiave "contexts", e con `[run] dynamic_context = test_function` nel
`.coveragerc` si genera un conflitto con `--cov-context=test` di
pytest-cov (warning "Conflicting dynamic contexts").
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assist.verification.sandbox import SandboxRunner

_MARK_START = "===ASSIST_COV_START==="
_MARK_END = "===ASSIST_COV_END==="

_COVERAGERC_CONTENT = "[json]\nshow_contexts = True\n"

_DRIVER_SOURCE_TEMPLATE = '''\
"""Driver eseguito in sandbox: lancia pytest con coverage a contesti
per-test e stampa il report JSON tra due marker sullo stdout, perche'
la workdir della sandbox viene cancellata prima che il chiamante
possa leggere i file prodotti su disco."""

import sys

import pytest

_MARK_START = {mark_start!r}
_MARK_END = {mark_end!r}

_ret = pytest.main([
    "-q",
    "--no-header",
    "-p",
    "no:cacheprovider",
    "--cov=" + {module_name!r},
    "--cov-context=test",
    "--cov-report=json:_assist_cov.json",
])

try:
    with open("_assist_cov.json", "r", encoding="utf-8") as _f:
        _content = _f.read()
except FileNotFoundError:
    _content = ""
except Exception:
    _content = ""

print(_MARK_START)
print(_content)
print(_MARK_END)
sys.exit(_ret)
'''


class CoverageMap:
    """Mappa {numero di riga -> insieme di test id} per un modulo.

    `available` e' False quando la mappa non ha potuto essere
    costruita (coverage/pytest-cov assenti nella sandbox, parsing del
    report fallito, marker non trovati sullo stdout, ecc.): in quel
    caso il chiamante deve ricadere sul comportamento "esegui tutta
    la suite per ogni mutante".
    """

    def __init__(
        self,
        line_tests: dict[int, set[str]] | None = None,
        available: bool = False,
    ) -> None:
        self.line_tests: dict[int, set[str]] = line_tests or {}
        self.available = available

    def tests_for_line(self, lineno: int) -> set[str]:
        """Ritorna i test id che coprono `lineno` (vuoto se nessuno)."""
        return set(self.line_tests.get(lineno, set()))

    def all_tests(self) -> set[str]:
        """Ritorna l'unione di tutti i test id presenti nella mappa."""
        result: set[str] = set()
        for tests in self.line_tests.values():
            result |= tests
        return result


def _normalize_context(context_id: str) -> str:
    """Normalizza un context id di coverage.py/pytest-cov a test node id.

    I context id hanno forma "test_file.py::test_name|run" (o
    "|setup"/"|teardown"); il context vuoto "" indica righe eseguite
    fuori da un test (import a livello di modulo, ecc.) e va
    scartato.
    """

    if not context_id or "::" not in context_id:
        return ""
    return context_id.split("|", 1)[0]


def build_coverage_map(
    source: str,
    module_name: str,
    test_source: str,
    test_file_name: str,
    sandbox: SandboxRunner,
    extra_files: dict[str, str] | None = None,
) -> CoverageMap:
    """Costruisce la mappa di copertura per-test eseguendo la suite
    una sola volta in sandbox con `coverage` a contesti dinamici.

    Non solleva mai eccezioni: se `coverage`/`pytest-cov` non sono
    disponibili nella sandbox, se lo stdout non contiene i marker
    attesi o se il report JSON non e' interpretabile, ritorna
    `CoverageMap(available=False)`.
    """

    driver_name = "_assist_cov_driver.py"
    driver_source = _DRIVER_SOURCE_TEMPLATE.format(
        mark_start=_MARK_START,
        mark_end=_MARK_END,
        module_name=module_name,
    )

    files: dict[str, str] = {
        f"{module_name}.py": source,
        test_file_name: test_source,
        ".coveragerc": _COVERAGERC_CONTENT,
        **(extra_files or {}),
        driver_name: driver_source,
    }

    try:
        result = sandbox.run_script(files=files, entry=driver_name)
    except Exception:
        return CoverageMap(available=False)

    stdout = result.stdout
    start = stdout.find(_MARK_START)
    end = stdout.find(_MARK_END)

    if start == -1 or end == -1 or end <= start:
        return CoverageMap(available=False)

    payload = stdout[start + len(_MARK_START) : end].strip()

    if not payload:
        return CoverageMap(available=False)

    try:
        data = json.loads(payload)
        file_data = data["files"][f"{module_name}.py"]
        contexts: dict[str, list[str]] = file_data["contexts"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return CoverageMap(available=False)

    line_tests: dict[int, set[str]] = {}
    for lineno_str, context_ids in contexts.items():
        try:
            lineno = int(lineno_str)
        except (TypeError, ValueError):
            continue

        tests = {_normalize_context(c) for c in context_ids}
        tests.discard("")

        if tests:
            line_tests[lineno] = tests

    return CoverageMap(line_tests=line_tests, available=True)
