
from assist.core.dependency_analyzer import (
    DependencyAnalyzer,
)
from assist.schemas.models import (
    FileMetadata,
)


class DependencyGraph:

    def build(
        self,
        files: list[FileMetadata],
    ) -> dict[str, list[str]]:

        graph = {}

        for file in files:

            imports = (
                DependencyAnalyzer.extract_imports(
                    file.path
                )
            )

            graph[file.path] = imports

        return graph