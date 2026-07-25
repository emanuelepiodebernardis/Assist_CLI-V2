from __future__ import annotations

from assist.schemas.models import (
    ArchitectureReport,
    Issue,
    ProjectGraph,
)


class ArchitectureAnalyzer:
    def detect_cycles(
        self,
        graph: ProjectGraph,
    ) -> ArchitectureReport:
        modules = {
            node.module
            for node in graph.files
        }

        adjacency = {
            node.module: [
                imported
                for imported in node.imports
                if imported in modules
            ]
            for node in graph.files
        }

        cycles = self._find_cycles(adjacency)

        issues = [
            Issue(
                severity="critical",
                message=(
                    "Cyclic dependency detected: "
                    + " -> ".join(cycle)
                ),
                location=cycle[0],
            )
            for cycle in cycles
        ]

        return ArchitectureReport(
            has_cycles=bool(cycles),
            cycles=cycles,
            issues=issues,
        )

    def _find_cycles(
        self,
        adjacency: dict[str, list[str]],
    ) -> list[list[str]]:
        visited: set[str] = set()
        on_stack: set[str] = set()
        stack: list[str] = []
        cycles: set[tuple[str, ...]] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            stack.append(node)
            on_stack.add(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in on_stack:
                    idx = stack.index(neighbor)
                    cycle = stack[idx:] + [neighbor]
                    cycles.add(self._canonical_cycle(cycle))

            stack.pop()
            on_stack.remove(node)

        for node in adjacency:
            if node not in visited:
                dfs(node)

        return [
            list(cycle)
            for cycle in sorted(cycles)
        ]

    def _canonical_cycle(
        self,
        cycle: list[str],
    ) -> tuple[str, ...]:
        core = cycle[:-1]

        variants: list[tuple[str, ...]] = []

        for i in range(len(core)):
            seq = core[i:] + core[:i]
            variants.append(tuple(seq + [seq[0]]))

        return min(variants)