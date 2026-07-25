from pathlib import Path

import pytest

from assist.verification.repo_config import (
    RepoVerifyConfig,
    is_excluded,
    load_repo_config,
)


def test_finds_config_in_same_dir(tmp_path: Path) -> None:
    (tmp_path / ".assist.yaml").write_text(
        "mutation_threshold: 0.9\nmax_mutants: 10\n",
        encoding="utf-8",
    )

    config = load_repo_config(tmp_path)

    assert config.mutation_threshold == 0.9
    assert config.max_mutants == 10
    assert config.sandbox_timeout_seconds is None


def test_finds_config_walking_up_with_git_marker(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".assist.yaml").write_text(
        "generate_boundary_tests: false\n",
        encoding="utf-8",
    )
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)

    config = load_repo_config(nested)

    assert config.generate_boundary_tests is False


def test_not_found_returns_defaults(tmp_path: Path) -> None:
    # Nessun marker di project root e nessun file .assist.yaml: la
    # risalita si ferma dopo _MAX_LEVELS livelli senza trovare nulla.
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    config = load_repo_config(nested)

    assert config == RepoVerifyConfig()
    assert config.mutation_threshold is None
    assert config.exclude == []


def test_malformed_yaml_raises_value_error_with_path(tmp_path: Path) -> None:
    bad_file = tmp_path / ".assist.yaml"
    bad_file.write_text("mutation_threshold: [unclosed\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_repo_config(tmp_path)

    assert str(bad_file) in str(exc_info.value)


def test_invalid_field_raises_value_error_with_path(tmp_path: Path) -> None:
    bad_file = tmp_path / ".assist.yaml"
    bad_file.write_text("mutation_threshold: 5.0\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_repo_config(tmp_path)

    assert str(bad_file) in str(exc_info.value)


def test_is_excluded_matches_subdir_glob(tmp_path: Path) -> None:
    config = RepoVerifyConfig(exclude=["migrations/*.py"])
    file_path = tmp_path / "migrations" / "0001_initial.py"

    assert is_excluded(file_path, config, base_dir=tmp_path) is True


def test_is_excluded_matches_filename_glob(tmp_path: Path) -> None:
    config = RepoVerifyConfig(exclude=["*_test.py"])
    file_path = tmp_path / "pkg" / "foo_test.py"

    assert is_excluded(file_path, config, base_dir=tmp_path) is True


def test_is_excluded_no_match(tmp_path: Path) -> None:
    config = RepoVerifyConfig(exclude=["migrations/*.py"])
    file_path = tmp_path / "pkg" / "core.py"

    assert is_excluded(file_path, config, base_dir=tmp_path) is False


def test_is_excluded_empty_patterns(tmp_path: Path) -> None:
    config = RepoVerifyConfig()
    file_path = tmp_path / "anything.py"

    assert is_excluded(file_path, config, base_dir=tmp_path) is False


def test_merged_with_partial_override() -> None:
    config = RepoVerifyConfig(
        mutation_threshold=0.9,
        generate_boundary_tests=False,
    )

    merged = config.merged_with(
        mutation_threshold=0.6,
        sandbox_timeout_seconds=30,
        max_mutants=40,
        generate_boundary_tests=True,
        max_fix_iterations=3,
    )

    assert merged == {
        "mutation_threshold": 0.9,
        "sandbox_timeout_seconds": 30,
        "max_mutants": 40,
        "generate_boundary_tests": False,
        "max_fix_iterations": 3,
    }


def test_merged_with_no_override_uses_globals() -> None:
    config = RepoVerifyConfig()

    merged = config.merged_with(
        mutation_threshold=0.6,
        sandbox_timeout_seconds=30,
        max_mutants=40,
        generate_boundary_tests=True,
        max_fix_iterations=3,
    )

    assert merged == {
        "mutation_threshold": 0.6,
        "sandbox_timeout_seconds": 30,
        "max_mutants": 40,
        "generate_boundary_tests": True,
        "max_fix_iterations": 3,
    }
