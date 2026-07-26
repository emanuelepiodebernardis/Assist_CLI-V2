from assist.schemas.models import (
    FunctionSymbol,
)

# Metodi/funzioni con decoratori che li rendono "usati" implicitamente
# da un framework (pytest, pydantic, abc, proprieta' Python) e che
# quindi non vanno mai segnalati come dead code, anche se non compaiono
# in nessuna chiamata esplicita raccolta staticamente. Il confronto e'
# fatto sull'ultimo segmento del decoratore (es. "pytest.fixture" ->
# "fixture") cosi' da coprire sia la forma qualificata che quella
# importata direttamente (es. "from pytest import fixture").
_FRAMEWORK_DECORATORS = {
    "property",
    "staticmethod",
    "classmethod",
    "validator",
    "field_validator",
    "abstractmethod",
    "fixture",
}

# Nomi convenzionali che un tool statico non puo' collegare a una
# chiamata esplicita (entry point, funzioni richiamate dal runtime
# tramite convenzione di nome) ma che non sono comunque dead code.
_CONVENTIONAL_NAMES = {
    "main",
}


def _is_dunder(name: str) -> bool:
    """Ritorna True se ``name`` e' un metodo speciale (es. ``__init__``)."""
    return (
        len(name) > 4
        and name.startswith("__")
        and name.endswith("__")
    )


def _has_framework_decorator(decorators: list[str]) -> bool:
    """Ritorna True se uno dei decoratori indica uso da parte di un
    framework (property, staticmethod, fixture pytest, validator...)."""
    for decorator in decorators:
        last_segment = decorator.rsplit(".", maxsplit=1)[-1]

        if last_segment in _FRAMEWORK_DECORATORS:
            return True

    return False


def _is_excluded_from_dead_code(function: FunctionSymbol) -> bool:
    """Determina se ``function`` va escluso dal controllo dead-code.

    Sono esclusi: metodi dunder, funzioni ``test_*`` (raccolte da
    pytest tramite convenzione di nome, non tramite chiamata esplicita),
    fixture pytest e metodi con decoratori di framework comuni
    (``property``, ``staticmethod``, ``classmethod``, ``validator``,
    ``field_validator``, ``abstractmethod``), e nomi convenzionali come
    ``main``.
    """
    if _is_dunder(function.name):
        return True

    if function.name.startswith("test_"):
        return True

    if function.name in _CONVENTIONAL_NAMES:
        return True

    if _has_framework_decorator(function.decorators):
        return True

    return False


class DeadCodeDetector:

    def detect_unused_functions(
        self,
        functions: list[FunctionSymbol],
        calls: list[str],
    ) -> list[str]:

        called_functions = set(calls)

        unused = []

        for function in functions:

            if _is_excluded_from_dead_code(function):
                continue

            if (
                function.name
                not in called_functions
            ):
                unused.append(
                    function.name
                )

        return unused
