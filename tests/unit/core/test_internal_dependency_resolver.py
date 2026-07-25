from assist.core.internal_dependency_resolver import (
    InternalDependencyResolver,
)


def test_resolve_internal_dependencies():

    imports = [
        "assist.core.registry",
        "os",
        "pathlib",
    ]

    project_files = [
        "assist/core/registry.py",
        "assist/core/orchestrator.py",
    ]

    internal = (
        InternalDependencyResolver.resolve(
            imports,
            project_files,
        )
    )

    assert (
        "assist.core.registry"
        in internal
    )

    assert len(internal) == 1