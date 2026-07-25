from assist.verification.dependency_collector import DependencyCollector


def test_collects_simple_local_import(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("from helpers import greet\n\ngreet()\n")

    helpers = tmp_path / "helpers.py"
    helpers.write_text("def greet():\n    print('hi')\n")

    result = DependencyCollector().collect(str(target))

    assert result == {"helpers.py": helpers.read_text(encoding="utf-8")}


def test_collects_package_import_via_init(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import pkg\n")

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    init_file = pkg_dir / "__init__.py"
    init_file.write_text("VALUE = 42\n")

    result = DependencyCollector().collect(str(target))

    assert result == {
        "pkg/__init__.py": init_file.read_text(encoding="utf-8")
    }


def test_collects_dotted_submodule_import(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import pkg\nfrom pkg.sub import value\n")

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    init_file = pkg_dir / "__init__.py"
    init_file.write_text("")
    sub_module = pkg_dir / "sub.py"
    sub_module.write_text("value = 1\n")

    result = DependencyCollector().collect(str(target))

    assert result["pkg/sub.py"] == sub_module.read_text(encoding="utf-8")
    assert result["pkg/__init__.py"] == init_file.read_text(encoding="utf-8")


def test_recursive_collection(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import helpers\n")

    helpers = tmp_path / "helpers.py"
    helpers.write_text("import utils\n\ndef helper():\n    return utils.value\n")

    utils = tmp_path / "utils.py"
    utils.write_text("value = 1\n")

    result = DependencyCollector().collect(str(target))

    assert set(result) == {"helpers.py", "utils.py"}
    assert result["helpers.py"] == helpers.read_text(encoding="utf-8")
    assert result["utils.py"] == utils.read_text(encoding="utf-8")


def test_stdlib_and_third_party_imports_are_ignored(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import os\nimport json\nfrom pathlib import Path\n")

    result = DependencyCollector().collect(str(target))

    assert result == {}


def test_target_itself_is_not_included(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import helpers\n")

    helpers = tmp_path / "helpers.py"
    helpers.write_text("value = 1\n")

    result = DependencyCollector().collect(str(target))

    assert "main.py" not in result


def test_max_files_limit_is_respected(tmp_path):
    imports = "\n".join(f"import mod{i}" for i in range(10))
    target = tmp_path / "main.py"
    target.write_text(imports + "\n")

    for i in range(10):
        (tmp_path / f"mod{i}.py").write_text(f"value_{i} = {i}\n")

    result = DependencyCollector().collect(str(target), max_files=3)

    assert len(result) <= 3


def test_unreadable_or_broken_syntax_file_is_skipped(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("import broken\nimport helpers\n")

    broken = tmp_path / "broken.py"
    broken.write_text("def broken(:\n    pass\n")

    helpers = tmp_path / "helpers.py"
    helpers.write_text("value = 1\n")

    result = DependencyCollector().collect(str(target))

    # broken.py viene comunque raccolto (e' leggibile), ma la sua
    # sintassi rotta non deve interrompere la raccolta degli altri
    # moduli ne' far fallire il collector.
    assert "helpers.py" in result
    assert result["helpers.py"] == helpers.read_text(encoding="utf-8")


def test_relative_import_from_dot_is_resolved(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("from . import helpers\n")

    helpers = tmp_path / "helpers.py"
    helpers.write_text("value = 1\n")

    result = DependencyCollector().collect(str(target))

    assert result == {"helpers.py": helpers.read_text(encoding="utf-8")}
