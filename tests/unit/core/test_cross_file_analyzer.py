from pathlib import Path

from assist.core.cross_file_analyzer import (
    CrossFileAnalyzer,
)

from assist.schemas.models import (
    FileMetadata,
)


def test_cross_file_analysis():

    metadata = FileMetadata(
        path="example.py",
        size_bytes=10,
        lines=3,
    )

    result = (
        CrossFileAnalyzer()
        .analyze([metadata])
    )

    assert result.imports == []