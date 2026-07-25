from assist.core.project_scanner import (
    ProjectScanner,
)


def test_scanner_returns_python_files(tmp_path):

    app = tmp_path / "app"

    app.mkdir()

    main_file = app / "main.py"

    main_file.write_text(
        "print('hello')",
        encoding="utf-8",
    )

    scanner = ProjectScanner()

    result = scanner.scan(
        str(app)
    )

    assert len(result) == 1

    assert result[0].path.endswith(
        "main.py"
    )


def test_scanner_excludes_venv(tmp_path):

    venv = tmp_path / "venv"

    venv.mkdir()

    ignored = venv / "ignored.py"

    ignored.write_text(
        "print('ignore')",
        encoding="utf-8",
    )

    scanner = ProjectScanner()

    result = scanner.scan(
        str(tmp_path)
    )

    assert result == []


def test_scanner_excludes_git_directory(tmp_path):

    git_dir = tmp_path / ".git"

    git_dir.mkdir()

    ignored = git_dir / "config.py"

    ignored.write_text(
        "print('ignore')",
        encoding="utf-8",
    )

    scanner = ProjectScanner()

    result = scanner.scan(
        str(tmp_path)
    )

    assert result == []