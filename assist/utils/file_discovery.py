from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
}


def discover_files(
    root: str,
) -> list[Path]:

    root_path = Path(root)

    if root_path.is_file():
        return [root_path]

    files = []

    for path in root_path.rglob("*"):

        if (
            path.is_file()
            and path.suffix in SUPPORTED_EXTENSIONS
        ):
            files.append(path)

    return files