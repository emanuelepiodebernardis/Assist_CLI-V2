"""Lettura robusta di file di testo con encoding eterogenei.

Un progetto reale contiene file UTF-8, Windows-1252, UTF-16 con BOM
e occasionalmente binari con estensione sbagliata. Un singolo file
"strano" non deve mai interrompere una verifica o una scansione.
"""

from pathlib import Path

_BOMS: list[tuple[bytes, str]] = [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


class BinaryFileError(ValueError):
    """Il file sembra binario: non ha senso trattarlo come testo."""


def safe_read_text(file_path: str | Path) -> str:
    """Legge un file di testo senza mai sollevare UnicodeDecodeError.

    Ordine: BOM espliciti -> UTF-8 -> Windows-1252/Latin-1 con
    sostituzione dei byte invalidi. I file binari (byte nulli senza
    BOM) sollevano BinaryFileError con messaggio chiaro.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    raw = path.read_bytes()

    for bom, encoding in _BOMS:
        if raw.startswith(bom):
            return raw.decode(encoding, errors="replace")

    if b"\x00" in raw:
        raise BinaryFileError(
            f"Il file sembra binario (byte nulli): {file_path}"
        )

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Windows-1252 decodifica qualunque byte: mai un crash.
        return raw.decode("cp1252", errors="replace")
