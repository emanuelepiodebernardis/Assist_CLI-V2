import json
import os
from pathlib import Path

import pytest

from assist.verification.hook_install import (
    install_claude_code_hook,
    install_pre_commit,
)


def test_install_pre_commit_writes_executable_script(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    hook_path = install_pre_commit(tmp_path)

    assert hook_path == tmp_path / ".git" / "hooks" / "pre-commit"
    content = hook_path.read_text(encoding="utf-8")
    assert "# assist-cli hook" in content
    assert "verify" in content
    assert os.access(hook_path, os.X_OK)


def test_install_pre_commit_no_git_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        install_pre_commit(tmp_path)


def test_install_pre_commit_existing_without_marker_raises(
    tmp_path: Path,
) -> None:
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    existing_hook = hooks_dir / "pre-commit"
    existing_hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")

    with pytest.raises(ValueError):
        install_pre_commit(tmp_path)

    # Il file esistente non deve essere toccato.
    assert existing_hook.read_text(encoding="utf-8") == (
        "#!/bin/sh\necho custom\n"
    )


def test_install_pre_commit_existing_with_marker_overwritten(
    tmp_path: Path,
) -> None:
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    existing_hook = hooks_dir / "pre-commit"
    existing_hook.write_text(
        "#!/bin/sh\n# assist-cli hook\necho vecchio\n", encoding="utf-8"
    )

    hook_path = install_pre_commit(tmp_path)

    content = hook_path.read_text(encoding="utf-8")
    assert "# assist-cli hook" in content
    assert "verify" in content
    assert "vecchio" not in content


def test_install_claude_code_hook_creates_settings(
    tmp_path: Path,
) -> None:
    settings_path = install_claude_code_hook(tmp_path)

    assert settings_path == tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))

    post_tool_use = data["hooks"]["PostToolUse"]
    assert len(post_tool_use) == 1
    assert post_tool_use[0]["matcher"] == "Edit|Write"
    hooks = post_tool_use[0]["hooks"]
    assert len(hooks) == 1
    assert hooks[0]["type"] == "command"
    assert "assist.cli.main verify" in hooks[0]["command"]


def test_install_claude_code_hook_merges_existing_keys(
    tmp_path: Path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"model": "opus"}), encoding="utf-8"
    )

    result_path = install_claude_code_hook(tmp_path)

    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data["model"] == "opus"
    assert len(data["hooks"]["PostToolUse"]) == 1


def test_install_claude_code_hook_idempotent(tmp_path: Path) -> None:
    install_claude_code_hook(tmp_path)
    settings_path = install_claude_code_hook(tmp_path)

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    post_tool_use = data["hooks"]["PostToolUse"]

    assert len(post_tool_use) == 1
    assert len(post_tool_use[0]["hooks"]) == 1
