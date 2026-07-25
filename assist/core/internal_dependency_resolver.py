from pathlib import Path


class InternalDependencyResolver:

    @staticmethod
    def resolve(
        imports: list[str],
        project_files: list[str],
    ) -> list[str]:

        project_modules = set()

        for file in project_files:

            path = Path(file)

            module = (
                str(path)
                .replace("\\", ".")
                .replace("/", ".")
                .replace(".py", "")
            )

            project_modules.add(module)

        internal = []

        for imp in imports:

            for module in project_modules:

                if (
                    imp == module
                    or imp.startswith(module)
                    or module.startswith(imp)
                ):
                    internal.append(module)

        return sorted(
            set(internal)
        )