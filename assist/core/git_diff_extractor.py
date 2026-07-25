from __future__ import annotations

import subprocess
from pathlib import Path

from assist.schemas.models import (
    FileDiff,
    GitDiff,
)


class GitDiffExtractionError(Exception):
    """Sollevata quando l'estrazione del diff fallisce.

    Cause tipiche:
    - Range git invalido (es. HEAD~999 in un repo nuovo)
    - Repository non e' un repo git valido
    - git non e' installato sulla macchina
    """


class GitDiffExtractor:
    """Estrae un diff git su un range specifico.

    Usa subprocess per chiamare git (no dipendenze python extra).
    Esegue due comandi git separati:
    - `git diff --numstat <range>` per gli aggregati per file
    - `git diff <range>` per il contenuto testuale completo

    L'output viene mappato sui modelli Pydantic FileDiff e GitDiff.
    """

    def __init__(
        self,
        repo_path: Path,
    ) -> None:

        self.repo_path = Path(repo_path)

    def extract(
        self,
        range_spec: str,
    ) -> GitDiff:
        """Estrae il diff per il range specificato.

        Args:
            range_spec: stringa accettata da git diff.
                Esempi validi:
                - "HEAD"            (working dir vs HEAD)
                - "HEAD~3"          (ultimi 3 commit)
                - "HEAD~3..HEAD"    (range esplicito)
                - "main..feature"   (diff tra branch)
                - "--cached"        (solo staged)

        Returns:
            GitDiff con files, aggregati, raw_diff.

        Raises:
            GitDiffExtractionError se git fallisce.
        """

        numstat_output = (
            self._run_git_diff_numstat(
                range_spec
            )
        )

        raw_diff = self._run_git_diff_raw(
            range_spec
        )

        files = self._parse_numstat(
            numstat_output,
            raw_diff,
        )

        return GitDiff(
            range_spec=range_spec,
            files=files,
            files_changed=len(files),
            total_additions=sum(
                file_diff.additions
                for file_diff in files
            ),
            total_deletions=sum(
                file_diff.deletions
                for file_diff in files
            ),
            raw_diff=raw_diff,
        )

    def _run_git_diff_numstat(
        self,
        range_spec: str,
    ) -> str:
        """Esegue git diff --numstat per ottenere gli aggregati.

        Output formato:
            <additions>\\t<deletions>\\t<filename>
        Una riga per ogni file modificato.

        File binari hanno '-' al posto dei numeri.
        """

        return self._run_git_command(
            [
                "diff",
                "--numstat",
                range_spec,
            ]
        )

    def _run_git_diff_raw(
        self,
        range_spec: str,
    ) -> str:
        """Esegue git diff per ottenere il contenuto testuale completo.

        E' l'output formattato standard con header diff, hunks,
        linee added/removed prefissate da + / -.
        """

        return self._run_git_command(
            [
                "diff",
                range_spec,
            ]
        )

    def _run_git_command(
        self,
        args: list[str],
    ) -> str:
        """Esegue un comando git nella repo_path.

        check=False: non solleviamo CalledProcessError perche'
        vogliamo gestire noi gli errori con un messaggio chiaro.
        """

        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                check=False,
            )

        except FileNotFoundError as exc:

            raise GitDiffExtractionError(
                "git executable not found on PATH"
            ) from exc

        if result.returncode != 0:

            raise GitDiffExtractionError(
                f"git command failed: "
                f"{' '.join(args)} | "
                f"stderr: {result.stderr.strip()}"
            )

        return result.stdout

    def _parse_numstat(
        self,
        numstat_output: str,
        raw_diff: str,
    ) -> list[FileDiff]:
        """Parsa l'output di git diff --numstat.

        Per ogni riga valida estrae path, additions, deletions
        e cerca nel raw_diff la sezione corrispondente al file
        (gli hunks specifici).

        File binari (additions o deletions == '-') sono inclusi
        con additions=0 e deletions=0.
        """

        files: list[FileDiff] = []

        for line in numstat_output.splitlines():

            stripped = line.strip()

            if not stripped:
                continue

            parts = stripped.split("\t")

            if len(parts) != 3:
                continue

            additions_raw, deletions_raw, path = parts

            additions = (
                self._safe_int(additions_raw)
            )

            deletions = (
                self._safe_int(deletions_raw)
            )

            hunks = self._extract_hunks_for_file(
                raw_diff,
                path,
            )

            files.append(
                FileDiff(
                    path=path,
                    additions=additions,
                    deletions=deletions,
                    hunks=hunks,
                )
            )

        return files

    @staticmethod
    def _safe_int(
        value: str,
    ) -> int:
        """Converte una stringa numstat in int.

        Restituisce 0 per file binari ('-')
        o valori non numerici.
        """

        try:
            return int(value)

        except ValueError:
            return 0

    @staticmethod
    def _extract_hunks_for_file(
        raw_diff: str,
        path: str,
    ) -> str:
        """Estrae la sezione del raw_diff relativa a un file specifico.

        Il diff git ha sezioni che iniziano con:
            diff --git a/<path> b/<path>

        Estrae da quella riga fino alla prossima "diff --git"
        (o fino alla fine del raw_diff).
        """

        marker = f"diff --git a/{path} b/{path}"

        start = raw_diff.find(marker)

        if start == -1:
            return ""

        next_section = raw_diff.find(
            "diff --git ",
            start + len(marker),
        )

        if next_section == -1:
            return raw_diff[start:]

        return raw_diff[start:next_section]