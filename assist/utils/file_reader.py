from pathlib import Path

from assist.utils.safe_text import safe_read_text


class FileReader:
    """Lettura file robusta agli encoding (UTF-8, BOM, cp1252)."""

    @staticmethod
    def read(
        file_path: str,
    ) -> str:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        if not path.is_file():
            raise IsADirectoryError(
                f"Not a file: {file_path}"
            )

        return safe_read_text(path)
