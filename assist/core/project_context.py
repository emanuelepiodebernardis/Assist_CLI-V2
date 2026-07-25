from __future__ import annotations

from assist.schemas.models import (
    ProjectContext,
    ProjectContextFile,
    ProjectGraph,
)


class ProjectContextBuilder:
    def build(
        self,
        graph: ProjectGraph,
        max_files: int = 8,
    ) -> ProjectContext:
        scored_files = [
            self._score_node(node)
            for node in graph.files
        ]

        scored_files.sort(
            key=lambda item: item.importance_score,
            reverse=True,
        )

        primary_files = scored_files[:max_files]

        entry_points = [
            file.module
            for file in scored_files
            if self._is_entry_point(file)
        ]

        summary = self._build_summary(
            total_files=len(graph.files),
            primary_files=primary_files,
            entry_points=entry_points,
        )

        return ProjectContext(
            root=graph.root,
            summary=summary,
            total_files=len(graph.files),
            entry_points=entry_points,
            primary_files=primary_files,
        )

    def _score_node(
        self,
        node,
    ) -> ProjectContextFile:
        dependency_score = len(node.imports)
        reverse_score = len(node.imported_by)
        size_penalty = min(node.size_bytes / 50000, 1.0)

        raw_score = (
            dependency_score * 0.35
            + reverse_score * 0.45
            + (1.0 - size_penalty) * 0.20
        )

        importance_score = max(0.0, min(raw_score / 5.0, 1.0))

        return ProjectContextFile(
            path=node.path,
            module=node.module,
            importance_score=importance_score,
            imports=node.imports,
            imported_by=node.imported_by,
        )

    def _is_entry_point(
        self,
        file: ProjectContextFile,
    ) -> bool:
        return (
            file.module.endswith("main")
            or file.module.endswith("__init__")
            or file.module in {"main", "app"}
            or len(file.imported_by) == 0
        )

    def _build_summary(
        self,
        total_files: int,
        primary_files: list[ProjectContextFile],
        entry_points: list[str],
    ) -> str:
        primary_modules = ", ".join(
            file.module
            for file in primary_files[:5]
        ) or "none"

        entry_points_text = ", ".join(entry_points) or "none"

        return (
            f"Repository contains {total_files} Python files. "
            f"Most central modules: {primary_modules}. "
            f"Entry points: {entry_points_text}."
        )