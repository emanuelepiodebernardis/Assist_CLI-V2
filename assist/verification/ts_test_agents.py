"""Agenti per la generazione di test TypeScript (vitest / fast-check).

Equivalenti TypeScript di `boundary_agent.py` e `property_agent.py`:
stesso principio (modello *fast*, economico, che genera molti
candidati a basso costo; l'utilita' reale viene provata dopo,
deterministicamente, da sandbox/mutation testing), stessa struttura
(system prompt + template, estrazione code-fence via regex,
validazioni sull'output, fallback a stringa vuota).

`TsBoundaryTestAgent` genera test puntuali vitest sui boundary/edge
case del modulo TS. `TsPropertyTestAgent` genera property-based test
vitest+fast-check: come nel caso Python con Hypothesis, il rischio
principale e' il falso positivo di una proprieta' inventata che non
e' garantita dal design del codice, quindi il system prompt istruisce
il modello a proporre solo proprieta' di cui e' certo dalla semantica
del codice letto.
"""

import re

from assist.llm.base import LLMClient

_CODE_BLOCK = re.compile(
    r"```(?:typescript|ts|javascript|js)?\s*\n(.*?)```", re.DOTALL
)


def _extract_code(raw: str) -> str:
    """Estrae il blocco di codice da una risposta del modello.

    Cerca prima un blocco delimitato da code-fence (con o senza
    identificatore di linguaggio tra `typescript`, `ts`, `javascript`,
    `js`); se non lo trova, e la risposta sembra gia' codice puro
    (inizia con `import`, `describe(`, `it(`, `test(` o un commento),
    la ritorna cosi' com'e'. Altrimenti ritorna stringa vuota.
    """

    match = _CODE_BLOCK.search(raw)

    if match:
        return match.group(1).strip()

    stripped = raw.strip()
    if stripped.startswith(("import ", "describe(", "it(", "test(", "//", "/*")):
        return stripped

    return ""


def _has_import_from_module(test_source: str, module_name: str) -> bool:
    """Verifica che il file importi dal modulo `./<module_name>`.

    Accetta sia apici doppi che singoli, es. `from "./calc"` o
    `from './calc'`.
    """

    pattern = re.compile(
        r"""from\s+["']\./""" + re.escape(module_name) + r"""["']"""
    )
    return pattern.search(test_source) is not None


def _count_test_cases(test_source: str) -> int:
    """Conta le occorrenze di `it(`/`test(` nel sorgente del file."""

    return len(re.findall(r"\b(?:it|test)\(", test_source))


class TsBoundaryTestAgent:
    """Genera file di test vitest sui boundary/edge case per un modulo TS."""

    _SYSTEM = (
        "Sei un ingegnere QA esperto in edge case per TypeScript. Generi "
        "SOLO codice di test vitest valido, senza spiegazioni. I test "
        "devono coprire boundary condition: zero, numeri negativi, "
        "stringhe vuote, array vuoti, valori null/undefined dove i tipi "
        "lo consentono, off-by-one, input estremi. Usa sempre "
        '`import {{ describe, it, expect }} from "vitest"` e importa il '
        'modulo sotto test con `import ... from "./{module_name}"`. Non '
        "usare mai `require(`, ne' mock, ne' dipendenze esterne oltre "
        "vitest."
    )

    _PROMPT_TEMPLATE = (
        "Modulo TypeScript da testare: `{module_name}`\n\n"
        "Sorgente:\n"
        "```typescript\n"
        "{source}\n"
        "```\n\n"
        "Scrivi un file di test vitest completo che importa "
        '`{{ describe, it, expect }}` da `"vitest"` e le funzioni/classi '
        'pubbliche del modulo da `"./{module_name}"`. Copri i boundary '
        "case di ogni funzione/classe pubblica esportata (zero, "
        "negativi, stringhe vuote, array vuoti, null/undefined dove "
        "ammessi dai tipi, off-by-one). Includi asserzioni specifiche "
        "sui valori attesi con `expect(...)`, non solo \"non lancia "
        "eccezioni\". Non usare `require(`. Massimo {max_tests} test "
        "(chiamate a `it(`/`test(`). Rispondi con un solo blocco di "
        "codice."
    )

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
    ) -> str:
        """Ritorna il sorgente di un file di test vitest, o stringa
        vuota se la generazione non produce codice valido.

        Un output e' considerato valido solo se: e' estraibile un
        blocco di codice, contiene "vitest" e almeno un `expect(`,
        importa dal modulo giusto (`"./<module_name>"` o
        `'./<module_name>'`), non usa `require(` e il numero di
        `it(`/`test(` non supera `max_tests`.
        """

        prompt = self._PROMPT_TEMPLATE.format(
            module_name=module_name,
            source=source,
            max_tests=self.max_tests,
        )

        system = self._SYSTEM.format(module_name=module_name)

        raw = self.llm.complete(prompt=prompt, system=system)

        test_source = _extract_code(raw)

        if not test_source:
            return ""

        if "vitest" not in test_source:
            return ""

        if "expect(" not in test_source:
            return ""

        if not _has_import_from_module(test_source, module_name):
            return ""

        if "require(" in test_source:
            return ""

        if _count_test_cases(test_source) > self.max_tests:
            return ""

        return test_source


class TsPropertyTestAgent:
    """Genera file di property-based test vitest+fast-check per un modulo TS."""

    _SYSTEM = (
        "Sei un ingegnere QA esperto in property-based testing con "
        "fast-check per TypeScript. Generi SOLO codice di test "
        "vitest+fast-check valido, senza spiegazioni. Ogni test verifica "
        "una PROPRIETA' generale del codice (invariante, idempotenza, "
        "monotonia, roundtrip, relazione tra input e output), MAI un "
        "singolo esempio puntuale. Proponi esclusivamente proprieta' di "
        "cui sei certo dalla semantica del codice fornito: una proprieta' "
        "inventata o non garantita dal design del codice e' un falso "
        "positivo e vale come veleno per l'evidenza, quindi in caso di "
        "dubbio ometti quella proprieta' invece di inventarla. Usa "
        '`import fc from "fast-check"` e `import {{ describe, it, expect }} '
        'from "vitest"`, e scrivi ogni proprieta\' come '
        '`it("...", () => {{ fc.assert(fc.property(...)); }})`. Importa '
        'il modulo sotto test da `"./{module_name}"`. Nessun mock, '
        "nessuna dipendenza esterna oltre vitest e fast-check."
    )

    _PROMPT_TEMPLATE = (
        "Modulo TypeScript da testare: `{module_name}`\n\n"
        "Sorgente:\n"
        "```typescript\n"
        "{source}\n"
        "```\n\n"
        "Scrivi un file di test vitest completo che importa "
        '`{{ describe, it, expect }}` da `"vitest"`, `fc` da '
        '`"fast-check"` e le funzioni/classi pubbliche del modulo da '
        '`"./{module_name}"`. Per ogni proprieta\' di cui sei certo, '
        'scrivi `it("descrizione", () => {{ fc.assert(fc.property(...)); '
        "}});` con arbitrary fast-check coerenti con i tipi degli "
        "argomenti (`fc.integer()`, `fc.string()`, `fc.array(...)`, "
        "ecc.) e verifica con `expect`/assert dentro la property che la "
        "proprieta' valga per ogni input generato. Esempi di proprieta' "
        "(adatta al codice reale, non inventare): l'output e' sempre non "
        "negativo, applicare due volte la funzione da' lo stesso "
        "risultato della prima (idempotenza), la lunghezza dell'output "
        "non supera quella dell'input, decodificare cio' che e' stato "
        "codificato ritorna l'input originale (roundtrip), l'ordine "
        "relativo si conserva (monotonia). Includi SOLO proprieta' "
        "garantite dalla semantica del codice mostrato. Massimo "
        "{max_properties} proprieta' (chiamate a `it(`). Esegui ogni "
        "property con `numRuns: {num_runs}`. Rispondi con un solo "
        "blocco di codice."
    )

    def __init__(
        self,
        llm: LLMClient,
        max_properties: int = 6,
        num_runs: int = 50,
    ) -> None:
        self.llm = llm
        self.max_properties = max_properties
        self.num_runs = num_runs

    def generate(
        self,
        source: str,
        module_name: str,
    ) -> str:
        """Ritorna il sorgente di un file di test vitest+fast-check, o
        stringa vuota se la generazione non produce codice valido.

        Un output e' considerato valido solo se: e' estraibile un
        blocco di codice, contiene "fast-check", "fc.assert" e
        "fc.property", importa dal modulo giusto
        (`"./<module_name>"` o `'./<module_name>'`) e il numero di
        `it(` non supera `max_properties` (troppe proprieta' in un
        colpo solo sono un segnale che il modello sta inventando
        invarianti deboli).
        """

        prompt = self._PROMPT_TEMPLATE.format(
            module_name=module_name,
            source=source,
            max_properties=self.max_properties,
            num_runs=self.num_runs,
        )

        system = self._SYSTEM.format(module_name=module_name)

        raw = self.llm.complete(prompt=prompt, system=system)

        test_source = _extract_code(raw)

        if not test_source:
            return ""

        if "fast-check" not in test_source:
            return ""

        if "fc.assert" not in test_source:
            return ""

        if "fc.property" not in test_source:
            return ""

        if not _has_import_from_module(test_source, module_name):
            return ""

        if _count_test_cases(test_source) > self.max_properties:
            return ""

        return test_source

    @staticmethod
    def harden(test_source: str, num_runs: int) -> str:
        """Garantisce un numero minimo di run fast-check nel file.

        Invece di manipolare ogni singola chiamata `fc.assert(...)` via
        regex su codice multilinea (fragile: bisogna gestire parentesi
        annidate, argomenti gia' presenti, formattazione variabile...),
        configura un profilo globale fast-check in testa al file con
        `fc.configureGlobal({{ numRuns: N }})`, che fast-check applica a
        ogni `fc.assert`/`fc.check` successivo del processo salvo
        override esplicito. E' quindi robusto indipendentemente da come
        il modello ha strutturato l'output.

        Se "numRuns" e' gia' presente nel sorgente (il modello lo ha
        gia' specificato esplicitamente in una chiamata), il sorgente
        viene ritornato invariato: l'idempotenza evita di sovrascrivere
        un valore scelto intenzionalmente con il profilo globale.
        """

        if "numRuns" in test_source:
            return test_source

        header = (
            'import fc0 from "fast-check";\n'
            f"fc0.configureGlobal({{ numRuns: {num_runs} }});\n"
        )

        return f"{header}\n{test_source}"
