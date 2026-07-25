from assist.schemas.models import (
    FunctionSymbol,
)


class DeadCodeDetector:

    def detect_unused_functions(
        self,
        functions: list[FunctionSymbol],
        calls: list[str],
    ) -> list[str]:

        called_functions = set(calls)

        unused = []

        for function in functions:

            if (
                function.name
                not in called_functions
            ):
                unused.append(
                    function.name
                )

        return unused