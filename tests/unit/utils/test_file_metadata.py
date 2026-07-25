from assist.utils.file_metadata import (
    build_file_metadata,
)


def test_build_metadata():

    content = "line1\nline2"

    metadata = build_file_metadata(
        "test.py",
        content,
    )

    assert metadata.path == "test.py"

    assert metadata.lines == 2

    assert metadata.size_bytes > 0