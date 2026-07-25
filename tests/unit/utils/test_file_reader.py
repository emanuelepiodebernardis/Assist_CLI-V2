from pathlib import Path

from assist.utils.file_reader import FileReader


def test_file_reader_reads_content(tmp_path: Path):
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    content = FileReader.read(str(file_path))

    assert content == "print('hello')"