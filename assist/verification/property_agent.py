"""Agente per la generazione di property-based test con Hypothesis.

Usa il modello *fast* (economico): a differenza dei test puntuali sui
boundary case, qui si chiede al modello di individuare PROPRIETA'
(invarianti, idempotenza, monotonia, roundtrip, relazioni tra input e
output) che devono valere per QUALSIASI input generato da Hypothesis.
Le proprieta' trovano classi di bug che i singoli esempi mancano.

Il rischio principale e' il falso positivo: una proprieta' inventata
che non e' vera per design del codice fallirebbe sempre, "avvelenando"
l'evidenza. Il prompt istruisce quindi il modello a proporre SOLO
proprieta' di cui e' certo dalla semantica del codice letto.
"""

import ast
import re

from assist.llm.base import LLMClient
from assist.schemas.models import SemanticAnalysis

_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

_SYSTEM = (
    "Sei un ingegnere QA esperto in property-based testing con "
    "Hypothesis. Generi SOLO codice pytest+Hypothesis valido, senza "
    "spiegazioni. Ogni test verifica una PROPRIETA' generale del "
    "codice (invariante, idempotenza, monotonia, roundtrip, relazione "
    "tra input e output), MAI un singolo esempio puntuale. Proponi "
    "esclusivamente proprieta' di cui sei certo dalla semantica del "
    "codice fornito: una proprieta' inventata o non garantita dal "
    "design del codice e' un falso positivo e vale come veleno per "
    "l'evidenza, quindi in caso di dubbio ometti quella proprieta' "
    "invece di inventarla. Usa sempre `@given` con strategie "
    "Hypothesis coerenti con i tipi degli argomenti e "
    "`@settings(max_examples=..., deadline=None)` su ogni test. "
    "Nessun mock, nessuna dipendenza esterna oltre pytest e hypothesis."
)

_PROMPT_TEMPLATE = """Modulo da testare: `{module_name}`

Funzioni e classi pubbliche:
{symbols}

Sorgente:
```python
{source}
```

Scrivi un file pytest completo che importa dal modulo `{module_name}`
(es. `from {module_name} import ...`) e da hypothesis
(`from hypothesis import given, settings, strategies as st`).
Per ogni proprieta' di cui sei certo, scrivi una funzione di test che
usa `@given(...)` con strategie appropriate ai tipi degli argomenti e
`@settings(max_examples={max_examples}, deadline=None, derandomize=True)`, e verifica
con `assert` che la proprieta' valga per ogni input generato. Esempi
di proprieta' (adatta al codice reale, non inventare): l'output e'
sempre non negativo, applicare due volte la funzione da' lo stesso
risultato della prima (idempotenza), la lunghezza dell'output non
supera quella dell'input, decodificare cio' che e' stato codificato
ritorna l'input originale (roundtrip), l'ordine relativo si conserva
(monotonia). Includi SOLO proprieta' garantite dalla semantica del
codice mostrato. Massimo {max_properties} funzioni di test.
Rispondi con un solo blocco di codice."""


class PropertyTestAgent:
    """Genera file di property-based test (Hypothesis) dal modulo dato."""

    def __init__(
        self,
        llm: LLMClient,
        max_properties: int = 6,
        max_examples: int = 50,
    ) -> None:
        self.llm = llm
        self.max_properties = max_properties
        self.max_examples = max_examples

    def generate(
        self,
        source: str,
        module_name: str,
        semantic: SemanticAnalysis | None = None,
    ) -> str:
        """Ritorna il sorgente di un file pytest+Hypothesis, o stringa
        vuota se la generazione non produce codice valido.

        Un output e' considerato valido solo se: e' estraibile un
        blocco di codice, il codice e' sintatticamente corretto,
        importa/usa effettivamente hypothesis con `@given`, e il
        numero di funzioni di test non supera `max_properties`
        (troppe proprieta' in un colpo solo sono un segnale che il
        modello sta inventando invarianti deboli).
        """

        symbols = self._describe_symbols(semantic)

        prompt = _PROMPT_TEMPLATE.format(
            module_name=module_name,
            symbols=symbols or "(analisi non disponibile: deducile dal sorgente)",
            source=source,
            max_properties=self.max_properties,
            max_examples=self.max_examples,
        )

        raw = self.llm.complete(prompt=prompt, system=_SYSTEM)

        test_source = self._extract_code(raw)

        if not test_source:
            return ""

        try:
            tree = ast.parse(test_source)
        except SyntaxError:
            return ""

        if "hypothesis" not in test_source:
            return ""

        if "@given" not in test_source:
            return ""

        test_function_count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
        )

        if test_function_count == 0 or test_function_count > self.max_properties:
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

    @staticmethod
    def harden(test_source: str, max_examples: int) -> str:
        """Garantisce un limite comune di esempi Hypothesis nel file.

        Invece di manipolare l'AST per iniettare `@settings(...)` su
        ogni singola funzione decorata con `@given` (fragile: bisogna
        gestire decoratori gia' presenti, import mancanti, ordine dei
        decoratori...), registra e carica un profilo Hypothesis globale
        in testa al file. Il profilo si applica a tutti i test del
        modulo, incluse eventuali funzioni senza `@settings` esplicito,
        ed e' quindi robusto indipendentemente da come il modello ha
        strutturato l'output.
        """

        profile_lines = (
            "from hypothesis import settings as _assist_settings\n"
            f'_assist_settings.register_profile("assist", '
            f"max_examples={max_examples}, deadline=None, derandomize=True)\n"
            '_assist_settings.load_profile("assist")\n'
        )

        return f"{profile_lines}\n{test_source}"
