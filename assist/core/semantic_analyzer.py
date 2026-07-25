import ast
from pathlib import Path

from assist.schemas.models import (
    ClassSymbol,
    FunctionSymbol,
    SemanticFileAnalysis,
)


class SemanticAnalyzer:
    def analyze_file(
        self,
        file_path: str,
    ) -> SemanticFileAnalysis:
        path = Path(file_path)

        if path.suffix != ".py":
            return SemanticFileAnalysis(path=str(path))

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        functions: list[FunctionSymbol] = []
        classes: list[ClassSymbol] = []
        imports: set[str] = set()
        calls: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

            elif isinstance(node, ast.Call):
                name = self._get_call_name(node.func)
                if name:
                    calls.add(name)

            elif isinstance(node, ast.FunctionDef):
                functions.append(
                    FunctionSymbol(
                        name=node.name,
                        complexity=1,
                        lineno=node.lineno,
                        end_lineno=getattr(node, "end_lineno", None),
                        decorators=[
                            self._get_name(dec)
                            for dec in node.decorator_list
                            if self._get_name(dec)
                        ],
                    )
                )

            elif isinstance(node, ast.ClassDef):
                methods = []

                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        methods.append(
                            FunctionSymbol(
                                name=child.name,
                                complexity=1,
                                lineno=child.lineno,
                                end_lineno=getattr(
                                    child,
                                    "end_lineno",
                                    None,
                                ),
                                decorators=[
                                    self._get_name(dec)
                                    for dec in child.decorator_list
                                    if self._get_name(dec)
                                ],
                            )
                        )

                classes.append(
                    ClassSymbol(
                        name=node.name,
                        lineno=node.lineno,
                        end_lineno=getattr(
                            node,
                            "end_lineno",
                            None,
                        ),
                        methods=methods,
                    )
                )

        return SemanticFileAnalysis(
            path=str(path),
            functions=functions,
            classes=classes,
            imports=sorted(imports),
            calls=sorted(calls),
        )

    def _get_name(
        self,
        node: ast.AST,
    ) -> str | None:

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            base = self._get_name(node.value)

            if base:
                return f"{base}.{node.attr}"

        return None

    def _get_call_name(
        self,
        node: ast.AST,
    ) -> str | None:

        return self._get_name(node)