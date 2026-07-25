from pathlib import Path


class FileReader:
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

        return path.read_text(
            encoding="utf-8"
        )