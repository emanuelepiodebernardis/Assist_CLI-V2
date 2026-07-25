import ast

from assist.schemas.models import (
    FunctionInfo,
    SemanticAnalysis,
)


class ComplexityAnalyzer:

    COMPLEXITY_NODES = (
        ast.If,
        ast.For,
        ast.While,
        ast.Try,
        ast.With,
        ast.BoolOp,
        ast.Match,
    )

    def analyze(
        self,
        tree: ast.AST,
        semantic: SemanticAnalysis,
    ) -> SemanticAnalysis:

        updated_functions = []

        for function in semantic.functions:

            complexity = self._compute_complexity(
                tree,
                function.name,
            )

            updated_functions.append(
                FunctionInfo(
                    name=function.name,
                    line_count=function.line_count,
                    complexity=complexity,
                    lineno=function.lineno,
                    end_lineno=function.end_lineno,
                    decorators=function.decorators,
                )
            )

        semantic.functions = updated_functions

        return semantic

    def _compute_complexity(
        self,
        tree: ast.AST,
        function_name: str,
    ) -> int:

        for node in ast.walk(tree):

            if (
                isinstance(node, ast.FunctionDef)
                and node.name == function_name
            ):

                complexity = 1

                for child in ast.walk(node):

                    if isinstance(
                        child,
                        self.COMPLEXITY_NODES,
                    ):
                        complexity += 1

                return complexity

        return 1