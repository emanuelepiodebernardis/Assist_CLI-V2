"""Agente per la generazione di test sui boundary/edge case.

Usa il modello *fast* (economico): genera molti candidati a basso
costo; la loro utilita' viene poi provata deterministicamente da
sandbox e mutation testing, quindi non serve un modello forte qui.
"""

import ast
import re

from assist.llm.base import LLMClient
from assist.schemas.models import SemanticAnalysis

_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

_SYSTEM = (
    "Sei un ingegnere QA esperto in edge case. Generi SOLO codice "
    "pytest valido, senza spiegazioni. I test devono coprire boundary "
    "condition: valori limite, zero, negativi, vuoti, None, off-by-one, "
    "input estremi. Nessun mock, nessuna dipendenza esterna oltre pytest."
)

_PROMPT_TEMPLATE = """Modulo da testare: `{module_name}`

Funzioni e classi pubbliche:
{symbols}

Sorgente:
```python
{source}
```

Scrivi un file pytest completo che importa dal modulo `{module_name}`
(es. `from {module_name} import ...`) e verifica i boundary case di ogni
funzione pubblica. Includi asserzioni specifiche sui valori attesi,
non solo "non solleva eccezioni". Massimo {max_tests} test.
Rispondi con un solo blocco di codice."""


class BoundaryTestAgent:
    def __init__(
        self,
        llm: LLMClient,
        max_tests: int = 12,
    ) -> None:
        self.llm = llm
        self.max_tests = max_tests

    def generate(
        self,
        source: str,
        module_name: str,
        semantic: SemanticAnalysis | None = None,
    ) -> str:
        """Ritorna il sorgente di un file di test pytest, o stringa
        vuota se la generazione non produce codice valido."""

        symbols = self._describe_symbols(semantic)

        prompt = _PROMPT_TEMPLATE.format(
            module_name=module_name,
            symbols=symbols or "(analisi non disponibile: deducile dal sorgente)",
            source=source,
            max_tests=self.max_tests,
        )

        raw = self.llm.complete(prompt=prompt, system=_SYSTEM)

        test_source = self._extract_code(raw)

        if not test_source:
            return ""

        try:
            ast.parse(test_source)
        except SyntaxError:
            return ""

        return test_source

    @staticmethod
    def _describe_symbols(
        semantic: SemanticAnalysis | None,
    ) -> str:
        if semantic is None:
            return ""

        lines: list[str] = []

        for fn in semantic.functions:
            lines.append(
                f"- funzione `{fn.name}` (complessita' {fn.complexity})"
            )

        for cls in semantic.classes:
            methods = ", ".join(m.name for m in cls.methods)
            lines.append(f"- classe `{cls.name}` (metodi: {methods})")

        return "\n".join(lines)

    @staticmethod
    def _extract_code(raw: str) -> str:
        match = _CODE_BLOCK.search(raw)

        if match:
            return match.group(1).strip()

        # Il modello potrebbe rispondere con solo codice, senza fence.
        stripped = raw.strip()
        if stripped.startswith(("import ", "from ", "def test", "#")):
            return stripped

        return ""
