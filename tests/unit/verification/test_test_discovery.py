from assist.verification.test_discovery import TestDiscovery


def test_class_is_not_collected_as_a_test():
    assert TestDiscovery.__test__ is False


def test_finds_test_in_same_directory(tmp_path):
    module = tmp_path / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    test_file = tmp_path / "test_calc.py"
    test_file.write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_finds_stem_test_suffix_in_same_directory(tmp_path):
    module = tmp_path / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    test_file = tmp_path / "calc_test.py"
    test_file.write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_prefers_same_directory_over_tests_dir(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    module = tmp_path / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    same_dir_test = tmp_path / "test_calc.py"
    same_dir_test.write_text("def test_add():\n    pass\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(same_dir_test.resolve())


def test_finds_test_in_tests_dir_walking_up(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)
    module = src_dir / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_calc.py"
    test_file.write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_finds_test_in_tests_unit_dir(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    src_dir = tmp_path / "assist" / "core"
    src_dir.mkdir(parents=True)
    module = src_dir / "scanner.py"
    module.write_text("class Scanner: pass\n")

    tests_unit_dir = tmp_path / "tests" / "unit"
    tests_unit_dir.mkdir(parents=True)
    test_file = tests_unit_dir / "test_scanner.py"
    test_file.write_text("def test_scan():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_finds_test_in_singular_test_dir(tmp_path):
    (tmp_path / "setup.py").write_text("# setup\n")

    src_dir = tmp_path / "lib"
    src_dir.mkdir()
    module = src_dir / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    test_dir = tmp_path / "test"
    test_dir.mkdir()
    test_file = test_dir / "test_calc.py"
    test_file.write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_returns_none_when_no_test_found(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    module = tmp_path / "lonely.py"
    module.write_text("x = 1\n")

    result = TestDiscovery().find_tests(str(module))

    assert result is None


def test_stops_walking_up_at_project_root(tmp_path):
    """Un test presente sopra la project root non deve essere trovato."""
    outer_tests = tmp_path / "tests"
    outer_tests.mkdir()
    (outer_tests / "test_calc.py").write_text("def test_add():\n    pass\n")

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text("[project]\n")

    module = project_root / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    result = TestDiscovery().find_tests(str(module))

    assert result is None


def test_respects_max_levels_bound_without_project_root(tmp_path):
    """Senza marker di project root, la ricerca si ferma dopo
    MAX_LEVELS livelli: un test esattamente al limite viene trovato,
    uno oltre il limite no."""
    within_bound_dir = tmp_path
    nested = within_bound_dir
    for name in ("a", "b", "c", "d", "e"):
        nested = nested / name
    nested.mkdir(parents=True)

    module = nested / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    tests_dir = within_bound_dir / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_calc.py"
    test_file.write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result == str(test_file.resolve())


def test_beyond_max_levels_bound_returns_none(tmp_path):
    within_bound_dir = tmp_path
    nested = within_bound_dir
    for name in ("a", "b", "c", "d", "e", "f"):
        nested = nested / name
    nested.mkdir(parents=True)

    module = nested / "calc.py"
    module.write_text("def add(a, b):\n    return a + b\n")

    tests_dir = within_bound_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("def test_add():\n    pass\n")

    result = TestDiscovery().find_tests(str(module))

    assert result is None
