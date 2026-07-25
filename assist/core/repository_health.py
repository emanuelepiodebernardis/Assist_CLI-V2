from assist.schemas.models import (
    Issue,
    ProjectGraph,
    RepositoryHealthReport,
)


class RepositoryHealthAnalyzer:

    HIGH_DEPENDENCY_THRESHOLD = 5

    def analyze(
        self,
        graph: ProjectGraph,
        cycles: list[list[str]],
    ) -> RepositoryHealthReport:

        total_files = len(graph.files)

        total_dependencies = sum(
            len(node.imports)
            for node in graph.files
        )

        highly_connected = []

        issues = []

        for node in graph.files:

            dependency_count = len(
                node.imports
            )

            if (
                dependency_count
                >= self.HIGH_DEPENDENCY_THRESHOLD
            ):
                highly_connected.append(
                    node.module
                )

                issues.append(
                    Issue(
                        severity="medium",
                        message=(
                            f"Highly coupled module: "
                            f"{node.module}"
                        ),
                        location=node.path,
                    )
                )

        score = 1.0

        score -= min(
            len(cycles) * 0.15,
            0.6,
        )

        score -= min(
            len(highly_connected) * 0.05,
            0.3,
        )

        score = max(score, 0.0)

        return RepositoryHealthReport(
            total_files=total_files,
            total_dependencies=(
                total_dependencies
            ),
            cyclic_dependencies=len(
                cycles
            ),
            highly_connected_files=(
                highly_connected
            ),
            health_score=round(score, 2),
            issues=issues,
        )