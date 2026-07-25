from __future__ import annotations

import ast
from pathlib import Path

from assist.core.project_scanner import ProjectScanner
from assist.schemas.models import (
    ProjectFileNode,
    ProjectGraph,
)
from assist.utils.file_reader import FileReader


class ProjectGraphBuilder:
    def __init__(
        self,
        scanner: ProjectScanner | None = None,
    ) -> None:
        self.scanner = scanner or ProjectScanner()

    def build(
        self,
        root: str,
    ) -> ProjectGraph:
        root_path = Path(root).resolve()
        scanned_files = self.scanner.scan(root)

        python_files = [
            file_meta
            for file_meta in scanned_files
            if Path(file_meta.path).suffix == ".py"
        ]

        module_map: dict[str, str] = {}
        for file_meta in python_files:
            path = Path(file_meta.path).resolve()
            module_name = self._path_to_module(root_path, path)
            module_map[module_name] = str(path)

        nodes: list[ProjectFileNode] = []

        for file_meta in python_files:
            path = Path(file_meta.path).resolve()
            module_name = self._path_to_module(root_path, path)
            content = FileReader.read(str(path))
            imports = self._extract_imports(
                content=content,
                current_module=module_name,
                module_map=module_map,
            )

            nodes.append(
                ProjectFileNode(
                    path=str(path),
                    module=module_name,
                    imports=imports,
                    imported_by=[],
                    size_bytes=file_meta.size_bytes,
                    lines=file_meta.lines,
                )
            )

        self._populate_imported_by(nodes)

        return ProjectGraph(
            root=str(root_path),
            files=nodes,
        )

    def _path_to_module(
        self,
        root_path: Path,
        file_path: Path,
    ) -> str:
        relative_path = file_path.relative_to(root_path).with_suffix("")

        parts = list(relative_path.parts)

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    def _extract_imports(
        self,
        content: str,
        current_module: str,
        module_map: dict[str, str],
    ) -> list[str]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_project_module(
                        alias.name,
                        module_map,
                    )
                    if resolved:
                        imports.add(resolved)

            elif isinstance(node, ast.ImportFrom):
                base_module = self._resolve_from_import(
                    current_module=current_module,
                    node=node,
                )

                if base_module:
                    resolved = self._resolve_project_module(
                        base_module,
                        module_map,
                    )
                    if resolved:
                        imports.add(resolved)

        return sorted(imports)

    def _resolve_from_import(
        self,
        current_module: str,
        node: ast.ImportFrom,
    ) -> str | None:
        if node.level == 0:
            return node.module

        current_parts = current_module.split(".")
        if len(current_parts) < node.level:
            return None

        base_parts = current_parts[:-node.level]

        if node.module:
            base_parts.extend(node.module.split("."))

        return ".".join(base_parts)

    def _resolve_project_module(
        self,
        import_name: str,
        module_map: dict[str, str],
    ) -> str | None:
        if import_name in module_map:
            return import_name

        parts = import_name.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in module_map:
                return candidate
            parts.pop()

        return None

    def _populate_imported_by(
        self,
        nodes: list[ProjectFileNode],
    ) -> None:
        module_to_node = {
            node.module: node
            for node in nodes
        }

        for node in nodes:
            for imported_module in node.imports:
                if imported_module in module_to_node:
                    module_to_node[imported_module].imported_by.append(
                        node.module
                    )