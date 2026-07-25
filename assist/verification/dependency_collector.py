"""Raccolta ricorsiva dei moduli locali importati da un file target.

Permette alla sandbox di eseguire codice multi-file: analizza l'AST
del target, individua gli import verso moduli locali (file `.py`
presenti nella directory del target) e li raccoglie ricorsivamente,
cosi' `SandboxRunner.run_pytest` puo' scrivere l'intero grafo di
dipendenze prima di eseguire i test.
"""

import ast
from pathlib import Path

DEFAULT_MAX_FILES = 20

MAX_RELATIVE_IMPORT_LEVEL = 1


class DependencyCollector:
    """Raccoglie i moduli Python locali importati (ricorsivamente)."""

    def collect(
        self,
        target_file: str,
        max_files: int = DEFAULT_MAX_FILES,
    ) -> dict[str, str]:
        """Raccoglie i moduli locali importati da `target_file`.

        Esplora l'AST del target ed estrae gli import verso moduli
        locali (un import `foo` o `from foo import x` e' locale se
        esiste `foo.py`, o `foo/__init__.py`, nella directory del
        target; `from foo.bar import x` cerca `foo/bar.py` sempre
        relativo alla directory del target). Segue ricorsivamente gli
        import trovati nei file raccolti, visitando ogni file una
        sola volta e fermandosi a `max_files` file raccolti. Il
        target stesso non viene incluso nel risultato.

        File illeggibili o con sintassi non valida vengono saltati
        senza interrompere la raccolta.

        Ritorna un dict {path_relativo_alla_dir_del_target: contenuto}.
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

            tree = self._parse(source)
            if tree is None:
                continue

            for module_path in self._local_imports(tree, base_dir):
                if module_path in visited:
                    continue

                visited.add(module_path)

                if len(collected) >= max_files:
                    break

                content = self._read(module_path)
                if content is None:
                    continue

                relative = self._relative_key(module_path, base_dir)
                if relative is None:
                    continue

                collected[relative] = content
                queue.append(module_path)

        return collected

    def _local_imports(
        self,
        tree: ast.Module,
        base_dir: Path,
    ) -> list[Path]:
        """Estrae dall'AST i path assoluti dei moduli locali importati,
        risolti sempre rispetto a `base_dir`."""
        found: list[Path] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_module(alias.name, base_dir)
                    if resolved is not None:
                        found.append(resolved)

            elif isinstance(node, ast.ImportFrom):
                found.extend(self._resolve_import_from(node, base_dir))

        return found

    def _resolve_import_from(
        self,
        node: ast.ImportFrom,
        base_dir: Path,
    ) -> list[Path]:
        """Risolve un `ast.ImportFrom`, gestendo anche gli import
        relativi risolvibili (livello 1, es. `from . import helpers`).
        Import relativi oltre il livello risolvibile vengono ignorati.
        """
        if node.level > MAX_RELATIVE_IMPORT_LEVEL:
            return []

        if node.level == MAX_RELATIVE_IMPORT_LEVEL and node.module is None:
            resolved_names = []
            for alias in node.names:
                resolved = self._resolve_module(alias.name, base_dir)
                if resolved is not None:
                    resolved_names.append(resolved)
            return resolved_names

        if node.module:
            resolved = self._resolve_module(node.module, base_dir)
            if resolved is not None:
                return [resolved]

        return []

    def _resolve_module(
        self,
        dotted_name: str,
        base_dir: Path,
    ) -> Path | None:
        """Risolve `foo` o `foo.bar` a un file `.py` locale, se
        esiste sotto `base_dir` (come modulo o come package)."""
        parts = dotted_name.split(".")
        candidate = base_dir.joinpath(*parts)

        module_file = candidate.with_suffix(".py")
        if module_file.is_file():
            return module_file.resolve()

        package_init = candidate / "__init__.py"
        if package_init.is_file():
            return package_init.resolve()

        return None

    def _relative_key(self, path: Path, base_dir: Path) -> str | None:
        """Ritorna la chiave da usare nel dict risultato: il path
        relativo a `base_dir`, con separatori `/`."""
        try:
            relative = path.relative_to(base_dir)
        except ValueError:
            return None

        return str(relative).replace("\\", "/")

    def _read(self, path: Path) -> str | None:
        """Legge `path`; ritorna `None` se non leggibile."""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def _parse(self, source: str) -> ast.Module | None:
        """Fa il parse AST di `source`; ritorna `None` se la
        sintassi non e' valida."""
        try:
            return ast.parse(source)
        except SyntaxError:
            return None
