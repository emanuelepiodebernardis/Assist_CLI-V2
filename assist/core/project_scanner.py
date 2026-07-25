from pathlib import Path

from assist.schemas.models import FileMetadata
from assist.utils.file_discovery import (
    discover_files,
)
from assist.utils.file_metadata import (
    build_file_metadata,
)
from assist.utils.file_reader import (
    FileReader,
)

EXCLUDED_DIRECTORIES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
}


class ProjectScanner:

    def scan(
        self,
        root: str,
    ) -> list[FileMetadata]:

        discovered = discover_files(root)

        filtered_files = []

        for path in discovered:

            if self._is_excluded(path):
                continue

            content = FileReader.read(
                str(path)
            )

            metadata = build_file_metadata(
                str(path),
                content,
            )

            filtered_files.append(
                metadata
            )

        return filtered_files

    def _is_excluded(
        self,
        path: Path,
    ) -> bool:

        parts = set(path.parts)

        return bool(
            parts & EXCLUDED_DIRECTORIES
        )