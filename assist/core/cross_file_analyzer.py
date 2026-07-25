
from assist.schemas.models import (
    CrossFileAnalysis,
    CrossFileReference,
)
from assist.utils.file_reader import (
    FileReader,
)


class CrossFileAnalyzer:

    def analyze(
        self,
        project_files: list,
    ) -> CrossFileAnalysis:

        imports = []

        function_calls = []

        for metadata in project_files:

            path = metadata.path

            if not path.endswith(".py"):
                continue

            try:
                content = FileReader.read(path)

            except Exception:
                continue

            lines = content.splitlines()

            for line in lines:

                stripped = line.strip()

                if stripped.startswith("import "):

                    imports.append(
                        CrossFileReference(
                            source_file=path,
                            target_file=(
                                stripped.replace(
                                    "import ",
                                    "",
                                )
                            ),
                            symbol="module_import",
                        )
                    )

                elif stripped.startswith(
                    "from "
                ):

                    parts = stripped.split()

                    if len(parts) >= 4:

                        imports.append(
                            CrossFileReference(
                                source_file=path,
                                target_file=parts[1],
                                symbol=parts[3],
                            )
                        )

                if "(" in stripped and ")" in stripped:

                    possible_call = (
                        stripped.split("(")[0]
                        .strip()
                    )

                    if possible_call.isidentifier():

                        function_calls.append(
                            CrossFileReference(
                                source_file=path,
                                target_file=path,
                                symbol=possible_call,
                            )
                        )

        return CrossFileAnalysis(
            imports=imports,
            function_calls=function_calls,
        )