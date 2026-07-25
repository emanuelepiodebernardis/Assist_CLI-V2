from assist.schemas.models import FileDiff, GitDiff
from assist.verification.diff_targets import (
    changed_lines_from_hunks,
    python_targets_from_diff,
)

HUNKS = """@@ -10,3 +12,4 @@ def foo():
 context
+nuova riga
 context
@@ -30 +40 @@
-vecchia
+nuova
"""


def test_changed_lines_from_hunks():
    lines = changed_lines_from_hunks(HUNKS)

    assert lines == {12, 13, 14, 15, 40}


def test_no_hunks_returns_empty():
    assert changed_lines_from_hunks("") == set()


def test_python_targets_filters_non_python():
    diff = GitDiff(
        range_spec="HEAD~1",
        files=[
            FileDiff(path="a.py", hunks="@@ -1 +1,2 @@\n+x\n+y\n"),
            FileDiff(path="README.md", hunks="@@ -1 +1 @@\n+z\n"),
        ],
    )

    targets = python_targets_from_diff(diff)

    assert set(targets) == {"a.py"}
    assert targets["a.py"] == {1, 2}
