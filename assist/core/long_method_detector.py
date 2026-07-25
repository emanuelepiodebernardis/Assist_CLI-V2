from assist.schemas.models import (
    LongMethodFinding,
    LongMethodReport,
    SemanticAnalysis,
)


class LongMethodDetector:

    LINE_THRESHOLD = 40

    def analyze(
        self,
        semantic: SemanticAnalysis,
    ) -> LongMethodReport:

        findings = []

        for function in semantic.functions:

            line_count = getattr(
                function,
                "line_count",
                0,
            )

            if (
                line_count
                >= self.LINE_THRESHOLD
            ):

                findings.append(
                    LongMethodFinding(
                        function_name=(
                            function.name
                        ),
                        line_count=line_count,
                        severity="medium",
                        recommendation=(
                            "Extract smaller "
                            "helper functions."
                        ),
                    )
                )

        return LongMethodReport(
            findings=findings
        )