from assist.schemas.models import (
    ClassSymbol,
    GodClassFinding,
    GodClassReport,
)


class GodClassDetector:

    METHOD_THRESHOLD = 10

    def analyze(
        self,
        classes: list[ClassSymbol],
    ) -> GodClassReport:

        findings = []

        for class_ in classes:

            method_count = len(
                class_.methods
            )

            if (
                method_count
                >= self.METHOD_THRESHOLD
            ):

                findings.append(
                    GodClassFinding(
                        class_name=class_.name,
                        method_count=method_count,
                        severity="high",
                        recommendation=(
                            "Split responsibilities "
                            "into smaller services."
                        ),
                    )
                )

        return GodClassReport(
            findings=findings
        )