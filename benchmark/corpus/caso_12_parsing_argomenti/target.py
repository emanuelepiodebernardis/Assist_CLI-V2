"""Parsing: estrazione dei primi N argomenti da una lista gia'
tokenizzata (es. argv gia' suddiviso)."""


def primi_argomenti(argomenti: list[str], n: int) -> list[str]:
    """Ritorna i primi `n` argomenti dalla lista.

    Bug: lo slice usa ``n - 1`` come limite superiore invece di
    ``n``, escludendo sempre l'ultimo argomento richiesto.
    """
    return argomenti[:n - 1]
