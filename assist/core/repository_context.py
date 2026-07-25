from assist.core.dependency_analyzer import (
    DependencyAnalyzer,
)
from assist.core.internal_dependency_resolver import (
    InternalDependencyResolver,
)
from assist.schemas.models import (
    FileMetadata,
)


class RepositoryContextBuilder:

    def build(
        self,
        target_file: str,
        project_files: list[FileMetadata],
    ) -> dict:

        imports = (
            DependencyAnalyzer.extract_imports(
                target_file
            )
        )

        project_paths = [
            file.path
            for file in project_files
        ]

        internal_dependencies = (
            InternalDependencyResolver.resolve(
                imports,
                project_paths,
            )
        )

        return {
            "imports": imports,
            "internal_dependencies": (
                internal_dependencies
            ),
            "project_size": len(project_files),
        }