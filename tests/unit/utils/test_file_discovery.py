from pathlib import Path

from assist.utils.file_discovery import discover_files


def test_discover_single_file(tmp_path):

    file_path = tmp_path / "main.py"

    file_path.write_text(
        "print('hello')",
        encoding="utf-8",
    )

    files = discover_files(
        str(file_path)
    )

    assert len(files) == 1

    assert files[0] == file_path


def test_discover_multiple_python_files(tmp_path):

    app_dir = tmp_path / "app"

    app_dir.mkdir()

    file_1 = app_dir / "main.py"
    file_2 = app_dir / "utils.py"

    file_1.write_text(
        "print('main')",
        encoding="utf-8",
    )

    file_2.write_text(
        "print('utils')",
        encoding="utf-8",
    )

    files = discover_files(
        str(app_dir)
    )

    assert len(files) == 2

    assert file_1 in files
    assert file_2 in files


def test_ignore_unsupported_extensions(tmp_path):

    app_dir = tmp_path / "project"

    app_dir.mkdir()

    py_file = app_dir / "main.py"
    txt_file = app_dir / "notes.txt"

    py_file.write_text(
        "print('hello')",
        encoding="utf-8",
    )

    txt_file.write_text(
        "ignored",
        encoding="utf-8",
    )

    files = discover_files(
        str(app_dir)
    )

    assert len(files) == 1

    assert py_file in files

    assert txt_file not in files


def test_empty_directory_returns_empty_list(tmp_path):

    empty_dir = tmp_path / "empty"

    empty_dir.mkdir()

    files = discover_files(
        str(empty_dir)
    )

    assert files == []