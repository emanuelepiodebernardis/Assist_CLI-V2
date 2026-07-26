"""Test di validazione strutturale del benchmark BM-1 (codice reale).

Non clona repository ne' esegue la pipeline (troppo lento per la
suite unit: ogni coppia richiede mutation testing in sandbox, alcuni
secondi ciascuna). Verifica solo che ``benchmark/run_realworld.py``
sia importabile e che la lista ``COPPIE`` sia ben formata, cosi' un
refactoring che rompe lo script viene individuato subito.
"""

from __future__ import annotations

from benchmark.run_realworld import _COPPIE_BY_NAME, COPPIE, Pair, _apply_rewrite


def test_coppie_non_vuota() -> None:
    """Il benchmark deve avere almeno 5 coppie, come da requisito BM-1."""
    assert len(COPPIE) >= 5


def test_coppie_almeno_tre_progetti() -> None:
    """Le coppie devono coprire almeno 3 progetti distinti."""
    progetti = {pair.project for pair in COPPIE}
    assert len(progetti) >= 3


def test_coppie_sono_istanze_pair() -> None:
    for pair in COPPIE:
        assert isinstance(pair, Pair)


def test_coppie_campi_obbligatori_valorizzati() -> None:
    """Ogni coppia deve avere progetto/url/modulo/test/nome/riscritture."""
    for pair in COPPIE:
        assert pair.project, f"{pair}: project mancante"
        assert pair.url.startswith("https://"), f"{pair}: url non valido"
        assert pair.module.endswith(".py"), f"{pair}: module non .py"
        assert pair.test.endswith(".py"), f"{pair}: test non .py"
        assert pair.name, f"{pair}: name mancante"
        assert len(pair.rewrite) >= 1, f"{pair}: nessuna riscrittura import"


def test_coppie_nomi_univoci() -> None:
    nomi = [pair.name for pair in COPPIE]
    assert len(nomi) == len(set(nomi))


def test_coppie_by_name_coerente() -> None:
    """L'indice per nome deve contenere esattamente le stesse coppie."""
    assert set(_COPPIE_BY_NAME) == {pair.name for pair in COPPIE}
    for name, pair in _COPPIE_BY_NAME.items():
        assert pair.name == name


def test_rewrite_e_tuple_di_coppie_stringa() -> None:
    for pair in COPPIE:
        for entry in pair.rewrite:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            old, new = entry
            assert isinstance(old, str) and old
            assert isinstance(new, str)
            assert old != new


def test_apply_rewrite_sostituisce_pattern_atteso() -> None:
    """La funzione di riscrittura sostituisce il pattern indicato."""
    source = "from pkg.mod import thing\n\nthing()\n"
    rewritten = _apply_rewrite(source, (("from pkg.mod import", "from mod import"),))
    assert "from mod import thing" in rewritten
    assert "from pkg.mod import" not in rewritten


def test_apply_rewrite_fallisce_se_pattern_assente() -> None:
    """Se il pattern non c'e' (drift upstream), deve fallire rumorosamente."""
    import pytest

    with pytest.raises(RuntimeError):
        _apply_rewrite("nessun import qui\n", (("from x import y", "from y import y"),))


def test_almeno_cinque_coppie_progetti_diversi_combinato() -> None:
    """Requisito di qualita' combinato: >=5 coppie da >=3 progetti."""
    progetti = {pair.project for pair in COPPIE}
    assert len(COPPIE) >= 5
    assert len(progetti) >= 3
