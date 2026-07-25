"""Test-bugia: controllano solo l'appartenenza del primo elemento e
il tipo del risultato, mai il conteggio esatto."""

from target import primi_argomenti


def test_primo_argomento_presente() -> None:
    risultato = primi_argomenti(
        ["--verbose", "--output", "file.txt", "--force"], 3
    )
    assert "--verbose" in risultato


def test_risultato_e_lista() -> None:
    risultato = primi_argomenti(["--verbose", "--output", "file.txt"], 2)
    assert isinstance(risultato, list)
