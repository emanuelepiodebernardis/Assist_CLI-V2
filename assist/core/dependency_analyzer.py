import ast
from pathlib import Path


class DependencyAnalyzer:

    @staticmethod
    def extract_imports(
        file_path: str,
    ) -> list[str]:

        path = Path(file_path)

        if path.suffix != ".py":
            return []

        source = path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(source)

        imports = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):

                if node.module:
                    imports.append(node.module)

        return sorted(set(imports))