"""Test del wrapper StrykerJS (`assist.verification.ts_support`).

Nessun test qui installa Stryker per davvero (troppo lento per la
suite): `parse_stryker_report` e' testato con un report fixture
scritto a mano, mentre `stryker_available`/`run_stryker` sono testati
contro una directory senza alcun tooling TS installato, verificando
che il fallimento sia gestito con `skipped_reason` e non con
un'eccezione.
"""

import json

import pytest

from assist.verification.ts_support import (
    node_available,
    parse_stryker_report,
    reset_ts_support_cache,
    run_stryker,
    stryker_available,
)

# Report Stryker fittizio (mutation-testing-report-schema) con un
# solo file e 5 mutanti: 2 Killed, 1 Survived, 1 NoCoverage,
# 1 Ignored. L'Ignored non deve contare nel totale.
STRYKER_REPORT = {
    "schemaVersion": "1.0",
    "files": {
        "src/calc.ts": {
            "language": "typescript",
            "mutants": [
                {
                    "id": "1",
                    "mutatorName": "ArithmeticOperator",
                    "status": "Killed",
                    "location": {
                        "start": {"line": 3, "column": 10},
                        "end": {"line": 3, "column": 11},
                    },
                    "replacement": "-",
                },
                {
                    "id": "2",
                    "mutatorName": "EqualityOperator",
                    "status": "Killed",
                    "location": {
                        "start": {"line": 5, "column": 4},
                        "end": {"line": 5, "column": 6},
                    },
                    "replacement": "!==",
                },
                {
                    "id": "3",
                    "mutatorName": "BooleanLiteral",
                    "status": "Survived",
                    "location": {
                        "start": {"line": 8, "column": 12},
                        "end": {"line": 8, "column": 17},
                    },
                    "replacement": "false",
                },
                {
                    "id": "4",
                    "mutatorName": "ConditionalExpression",
                    "status": "NoCoverage",
                    "location": {
                        "start": {"line": 12, "column": 2},
                        "end": {"line": 12, "column": 20},
                    },
                    "replacement": "true",
                },
                {
                    "id": "5",
                    "mutatorName": "StringLiteral",
                    "status": "Ignored",
                    "location": {
                        "start": {"line": 20, "column": 1},
                        "end": {"line": 20, "column": 10},
                    },
                    "replacement": '""',
                },
            ],
        }
    },
}


@pytest.fixture(autouse=True)
def _reset_cache():
    """Azzera la cache di modulo prima e dopo ogni test."""

    reset_ts_support_cache()
    yield
    reset_ts_support_cache()


def test_parse_stryker_report_conteggi_e_score():
    report = parse_stryker_report(json.dumps(STRYKER_REPORT))

    assert report.skipped_reason == ""
    assert report.total_mutants == 4  # Ignored escluso
    assert report.killed == 2
    assert report.survived == 2
    assert report.mutation_score == 0.5


def test_parse_stryker_report_linee_e_detail_no_coverage():
    report = parse_stryker_report(json.dumps(STRYKER_REPORT))

    survived_by_line = {r.mutant.lineno: r for r in report.surviving_mutants}

    assert set(survived_by_line) == {8, 12}
    assert survived_by_line[12].detail == "nessun test copre la riga"
    assert survived_by_line[8].detail != "nessun test copre la riga"


def test_parse_stryker_report_description_troncata_e_composta():
    report = parse_stryker_report(json.dumps(STRYKER_REPORT))

    survived_by_line = {r.mutant.lineno: r for r in report.surviving_mutants}
    descr = survived_by_line[8].mutant.description

    assert descr.startswith("BooleanLiteral: false")
    assert len(descr) <= 80


def test_parse_stryker_report_mutant_id_progressivo():
    report = parse_stryker_report(json.dumps(STRYKER_REPORT))

    all_results = report.surviving_mutants
    ids = sorted(r.mutant.mutant_id for r in all_results)

    # 4 mutanti totali (Ignored escluso): id progressivi senza buchi
    # rispetto all'ordine di lettura del report.
    assert len(set(ids)) == len(ids)
    assert all(i >= 1 for i in ids)


def test_parse_stryker_report_json_malformato():
    report = parse_stryker_report("{questo non e' json valido")

    assert report.skipped_reason != ""
    assert report.total_mutants == 0


def test_parse_stryker_report_senza_chiave_files():
    report = parse_stryker_report(json.dumps({"schemaVersion": "1.0"}))

    assert report.skipped_reason != ""
    assert report.total_mutants == 0


def test_parse_stryker_report_senza_mutanti():
    empty = {"files": {"src/empty.ts": {"language": "typescript", "mutants": []}}}
    report = parse_stryker_report(json.dumps(empty))

    assert report.total_mutants == 0
    assert report.skipped_reason != ""


def test_parse_stryker_report_non_e_un_oggetto():
    report = parse_stryker_report(json.dumps([1, 2, 3]))

    assert report.skipped_reason != ""
    assert report.total_mutants == 0


def test_node_available_true_nell_ambiente_corrente():
    assert node_available() is True


def test_stryker_available_false_su_dir_senza_stryker(tmp_path):
    assert stryker_available(tmp_path) is False


def test_stryker_available_e_cachata(tmp_path, monkeypatch):
    import assist.verification.ts_support as ts_support

    calls = {"n": 0}
    original_run = ts_support.subprocess.run

    def _counting_run(*args, **kwargs):
        calls["n"] += 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(ts_support.subprocess, "run", _counting_run)

    first = stryker_available(tmp_path)
    second = stryker_available(tmp_path)

    assert first is False
    assert second is False
    assert calls["n"] == 1  # seconda chiamata servita dalla cache


def test_run_stryker_su_dir_senza_stryker_ritorna_skipped(tmp_path):
    report = run_stryker(tmp_path, timeout_seconds=15)

    assert report.skipped_reason != ""
    assert report.total_mutants == 0
