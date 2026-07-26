"""Test della lettura robusta agli encoding."""

import pytest

from assist.utils.safe_text import (
    BinaryFileError,
    safe_read_text,
)


def test_utf8_normale(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 'ciao'\n", encoding="utf-8")

    assert safe_read_text(f) == "x = 'ciao'\n"


def test_utf8_con_bom(tmp_path):
    f = tmp_path / "a.py"
    f.write_bytes(b"\xef\xbb\xbfx = 1\n")

    assert safe_read_text(f) == "x = 1\n"


def test_utf16_con_bom(tmp_path):
    f = tmp_path / "a.py"
    f.write_bytes("x = 'caffè'\n".encode("utf-16"))

    assert "caffè" in safe_read_text(f)


def test_windows_1252(tmp_path):
    f = tmp_path / "a.py"
    # è in cp1252 = 0xE8, invalido come UTF-8
    f.write_bytes(b"# commento con \xe8 accento\nx = 1\n")

    result = safe_read_text(f)

    assert "x = 1" in result
    assert "è" in result


def test_file_binario_solleva_errore_chiaro(tmp_path):
    f = tmp_path / "a.py"
    f.write_bytes(b"\x00\x01\x02binario\x00")

    with pytest.raises(BinaryFileError):
        safe_read_text(f)


def test_file_mancante(tmp_path):
    with pytest.raises(FileNotFoundError):
        safe_read_text(tmp_path / "manca.py")


def test_filereader_non_crasha_su_cp1252(tmp_path):
    from assist.utils.file_reader import FileReader

    f = tmp_path / "a.py"
    f.write_bytes(b"nome = 'Nicol\xf2'\n")

    assert "Nicol" in FileReader.read(str(f))
