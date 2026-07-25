from pathlib import Path

from assist.schemas.models import FileMetadata


def build_file_metadata(
    file_path: str,
    content: str,
) -> FileMetadata:

    path = Path(file_path)

    return FileMetadata(
        path=str(path),
        size_bytes=len(
            content.encode("utf-8")
        ),
        lines=len(
            content.splitlines()
        ),
    )