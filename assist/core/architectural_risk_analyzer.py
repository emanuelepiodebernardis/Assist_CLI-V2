from assist.schemas.models import (
    ArchitecturalRisk,
    ArchitecturalRiskReport,
    ProjectGraph,
)


class ArchitecturalRiskAnalyzer:

    HIGH_COUPLING_THRESHOLD = 10

    def analyze(
        self,
        graph: ProjectGraph,
    ) -> ArchitecturalRiskReport:

        risks = []

        for node in graph.files:

            dependency_count = len(
                node.imports
            )

            if (
                dependency_count
                >= self.HIGH_COUPLING_THRESHOLD
            ):

                risks.append(
                    ArchitecturalRisk(
                        risk_type=(
                            "high_coupling"
                        ),
                        severity="high",
                        file=node.path,
                        description=(
                            f"{node.path} has "
                            f"{dependency_count} "
                            "dependencies."
                        ),
                    )
                )

            if dependency_count == 0:

                risks.append(
                    ArchitecturalRisk(
                        risk_type=(
                            "isolated_module"
                        ),
                        severity="medium",
                        file=node.path,
                        description=(
                            f"{node.path} is isolated "
                            "from the repository."
                        ),
                    )
                )

        return ArchitecturalRiskReport(
            risks=risks
        )