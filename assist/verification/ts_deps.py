"""Raccolta ricorsiva dei moduli TS/JS locali importati da un file target.

Analogo di `assist.verification.dependency_collector.DependencyCollector`
ma per TypeScript/JavaScript: non esiste un parser TS nel progetto, quindi
gli import vengono estratti con una regex sugli statement piu' comuni
(`import ... from "./x"`, `export ... from "./x"`, `import("./x")`
dinamico) invece che dall'AST. Solo gli import RELATIVI (che iniziano con
``.``) vengono seguiti: i pacchetti npm (``"vitest"``, ``"react"``, ...)
non hanno un file locale risolvibile e vengono ignorati.

Permette a `TsValidatedFixLoop`/`TsSandboxRunner` di eseguire in sandbox
un modulo TS che dipende da altri file locali, raccogliendo l'intero
grafo di dipendenze prima del run vitest.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from assist.utils.safe_text import safe_read_text

DEFAULT_MAX_FILES = 20

# Cattura lo specifier di import/export relativo: `from "./x"`,
# `export ... from "../y/z"`, `import("./x")` dinamico. Il gruppo
# catturato deve iniziare con "." (import relativo): i pacchetti npm
# (senza "." iniziale) non vengono catturati.
_IMPORT_RE = re.compile(r"""(?:from|import\()\s*["'](\.[^"']+)["']""")

# Estensioni provate, in ordine, quando lo specifier non ne ha gia' una.
_RESOLVE_EXTENSIONS = (".ts", ".tsx", ".js")

# Estensioni "note": se lo specifier le ha gia', si verifica solo
# l'esistenza del file cosi' com'e', senza altri tentativi.
_KNOWN_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json")


class TsDependencyCollector:
    """Raccoglie i moduli TS/JS locali importati (ricorsivamente)."""

    def collect(
        self,
        target_file: str | Path,
        max_files: int = DEFAULT_MAX_FILES,
    ) -> dict[str, str]:
        """Raccoglie i moduli TS/JS locali importati da `target_file`.

        Estrae dal sorgente del target gli import/export relativi
        (``./x``, ``../y/z``) e li risolve rispetto alla directory del
        file che li dichiara, provando nell'ordine ``<spec>.ts``,
        ``<spec>.tsx``, ``<spec>.js``, ``<spec>/index.ts`` (se lo
        specifier non ha gia' un'estensione nota). Segue
        ricorsivamente gli import trovati nei file raccolti, visitando
        ogni file risolto una sola volta e fermandosi a `max_files`
        file raccolti. Il target stesso non viene incluso nel
        risultato.

        File irrisolvibili o illeggibili vengono saltati senza
        interrompere la raccolta.

        Ritorna un dict ``{path_relativo_alla_dir_del_target (posix):
        contenuto}``: il path puo' contenere ``../`` se il file
        importato si trova fuori dalla directory del target.
        """
        target = Path(target_file).resolve()
        base_dir = target.parent

        collected: dict[str, str] = {}
        visited: set[Path] = {target}
        queue: list[Path] = [target]

        while queue and len(collected) < max_files:
            current = queue.pop(0)

            source = self._read(current)
            if source is None:
                continue

            for spec in _IMPORT_RE.findall(source):
                resolved = self._resolve(spec, current.parent)
                if resolved is None or resolved in visited:
                    continue

                visited.add(resolved)

                if len(collected) >= max_files:
                    break

                content = self._read(resolved)
                if content is None:
                    continue

                relative = self._relative_key(resolved, base_dir)
                if relative is None:
                    continue

                collected[relative] = content
                queue.append(resolved)

        return collected

    def _resolve(self, spec: str, from_dir: Path) -> Path | None:
        """Risolve uno specifier di import relativo (es. ``./helper``,
        ``../shared/util``) a un file esistente, relativo a
        `from_dir` (la directory del file che lo importa)."""
        base = (from_dir / spec).resolve()

        if base.suffix in _KNOWN_EXTENSIONS:
            return base if base.is_file() else None

        for ext in _RESOLVE_EXTENSIONS:
            candidate = Path(f"{base}{ext}")
            if candidate.is_file():
                return candidate

        index_candidate = base / "index.ts"
        if index_candidate.is_file():
            return index_candidate

        return None

    def _relative_key(self, path: Path, base_dir: Path) -> str | None:
        """Ritorna la chiave da usare nel dict risultato: il path
        relativo a `base_dir` (con eventuali ``..``), separatori
        posix."""
        try:
            relative = os.path.relpath(path, base_dir)
        except ValueError:
            return None

        return relative.replace("\\", "/")

    def _read(self, path: Path) -> str | None:
        """Legge `path` con `safe_read_text`; ritorna `None` se non
        leggibile (mancante, directory, binario, ecc.)."""
        try:
            return safe_read_text(path)
        except (OSError, ValueError):
            return None
