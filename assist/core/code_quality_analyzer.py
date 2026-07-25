import ast

from assist.core.architectural_risk_analyzer import ArchitecturalRiskAnalyzer
from assist.core.complexity_analyzer import ComplexityAnalyzer
from assist.core.dead_code_detector import DeadCodeDetector
from assist.core.god_class_detector import GodClassDetector
from assist.core.long_method_detector import LongMethodDetector
from assist.schemas.models import CodeQualityReport, ProjectGraph, SemanticAnalysis


class CodeQualityAnalyzer:
    def analyze(
        self,
        semantic: SemanticAnalysis,
        graph: ProjectGraph,
        tree: ast.AST | None = None,
    ) -> CodeQualityReport:
        dead_functions = DeadCodeDetector().detect_unused_functions(
            semantic.functions,
            semantic.calls,
        )

        long_methods = LongMethodDetector().analyze(semantic)

        god_classes = GodClassDetector().analyze(semantic.classes)

        if tree is not None:
            semantic_with_complexity = ComplexityAnalyzer().analyze(
                tree,
                semantic.model_copy(deep=True),
            )
            complexity_warnings = [
                function.name
                for function in semantic_with_complexity.functions
                if function.complexity > 1
            ]
        else:
            complexity_warnings = [
                function.name
                for function in semantic.functions
                if function.complexity > 1 or function.line_count >= 40
            ]

        risks = ArchitecturalRiskAnalyzer().analyze(graph)

        return CodeQualityReport(
            complexity_warnings=complexity_warnings,
            dead_functions=dead_functions,
            architectural_risks=[
                risk.description for risk in risks.risks
            ],
            long_methods=[
                finding.function_name
                for finding in long_methods.findings
            ],
            god_classes=[
                finding.class_name
                for finding in god_classes.findings
            ],
        )