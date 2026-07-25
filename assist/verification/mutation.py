"""Motore di mutation testing basato su AST.

Genera varianti ("mutanti") del codice sorgente cambiando un
operatore o una costante alla volta, poi esegue i test contro ogni
mutante. Se i test passano anche sul codice mutato, il mutante e'
"sopravvissuto": i test non verificano quel comportamento.

E' la prova deterministica della qualita' dei test — il pezzo che
gli AI code reviewer basati solo su LLM non hanno.
"""

import ast
import copy
import hashlib

from assist.verification.coverage_map import CoverageMap
from assist.verification.evidence import (
    Mutant,
    MutantResult,
    MutationReport,
)
from assist.verification.sandbox import SandboxRunner

_COMPARE_SWAPS: dict[type, type] = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}

_BINOP_SWAPS: dict[type, type] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Add,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Div,
    ast.Mod: ast.FloorDiv,
}

_BOOLOP_SWAPS: dict[type, type] = {
    ast.And: ast.Or,
    ast.Or: ast.And,
}


class _SiteCollector(ast.NodeVisitor):
    """Prima passata: conta i punti mutabili del sorgente."""

    def __init__(self) -> None:
        self.sites: list[tuple[int, str]] = []
        # Stack dell'ultimo statement del body di ogni funzione
        # annidata attualmente in visita (None se il body e' vuoto).
        self._function_stack: list[ast.stmt | None] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.body[-1] if node.body else None)
        self.generic_visit(node)
        self._function_stack.pop()

    # Le funzioni async condividono la stessa nozione di "corpo" e
    # devono essere tracciate allo stesso modo.
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, node: ast.Return) -> None:
        self.generic_visit(node)
        if self._function_stack and self._function_stack[-1] is not node:
            self.sites.append((node.lineno, "rimozione return anticipato"))

    def visit_Compare(self, node: ast.Compare) -> None:
        self.generic_visit(node)
        op = node.ops[0]
        if type(op) in _COMPARE_SWAPS:
            new_op = _COMPARE_SWAPS[type(op)].__name__
            self.sites.append(
                (
                    node.lineno,
                    f"operatore di confronto {_sym(op)} -> {_sym_name(new_op)}",
                )
            )

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self.generic_visit(node)
        if type(node.op) in _BINOP_SWAPS:
            new_op = _BINOP_SWAPS[type(node.op)].__name__
            self.sites.append(
                (
                    node.lineno,
                    f"operatore aritmetico {_sym(node.op)} -> {_sym_name(new_op)}",
                )
            )

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.generic_visit(node)
        if type(node.op) in _BOOLOP_SWAPS:
            new_op = _BOOLOP_SWAPS[type(node.op)].__name__
            self.sites.append(
                (
                    node.lineno,
                    f"operatore booleano {_sym(node.op)} -> {_sym_name(new_op)}",
                )
            )

    def visit_If(self, node: ast.If) -> None:
        self.generic_visit(node)
        self.sites.append((node.test.lineno, "negazione condizione if"))

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.generic_visit(node)
        if isinstance(node.slice, ast.Slice) and node.slice.upper is not None:
            self.sites.append((node.lineno, "slice off-by-one (upper - 1)"))

    def visit_Expr(self, node: ast.Expr) -> None:
        self.generic_visit(node)
        if isinstance(node.value, ast.Call):
            self.sites.append((node.lineno, "rimozione chiamata"))

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool):
            self.sites.append(
                (node.lineno, f"costante booleana {node.value} -> {not node.value}")
            )
        elif isinstance(node.value, int) and abs(node.value) < 1_000_000:
            self.sites.append(
                (
                    node.lineno,
                    f"costante intera {node.value} -> {node.value + 1} (off-by-one)",
                )
            )


class _Mutator(ast.NodeTransformer):
    """Seconda passata: applica la mutazione al sito `target_index`."""

    def __init__(self, target_index: int) -> None:
        self.counter = -1
        self.target = target_index
        self.applied = False
        # Stack dell'ultimo statement del body di ogni funzione
        # annidata attualmente in visita (None se il body e' vuoto).
        self._function_stack: list[ast.stmt | None] = []

    def _is_target(self) -> bool:
        self.counter += 1
        return self.counter == self.target

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._function_stack.append(node.body[-1] if node.body else None)
        self.generic_visit(node)
        self._function_stack.pop()
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if (
            self._function_stack
            and self._function_stack[-1] is not node
            and self._is_target()
        ):
            self.applied = True
            return ast.copy_location(ast.Pass(), node)
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if type(node.ops[0]) in _COMPARE_SWAPS and self._is_target():
            node.ops[0] = _COMPARE_SWAPS[type(node.ops[0])]()
            self.applied = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if type(node.op) in _BINOP_SWAPS and self._is_target():
            node.op = _BINOP_SWAPS[type(node.op)]()
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if type(node.op) in _BOOLOP_SWAPS and self._is_target():
            node.op = _BOOLOP_SWAPS[type(node.op)]()
            self.applied = True
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if self._is_target():
            node.test = ast.copy_location(
                ast.UnaryOp(op=ast.Not(), operand=node.test), node.test
            )
            self.applied = True
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.slice, ast.Slice)
            and node.slice.upper is not None
            and self._is_target()
        ):
            original_upper = node.slice.upper
            node.slice.upper = ast.copy_location(
                ast.BinOp(
                    left=original_upper, op=ast.Sub(), right=ast.Constant(value=1)
                ),
                node,
            )
            self.applied = True
        return node

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Call) and self._is_target():
            self.applied = True
            return ast.copy_location(ast.Pass(), node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool):
            if self._is_target():
                self.applied = True
                return ast.copy_location(
                    ast.Constant(value=not node.value), node
                )
        elif isinstance(node.value, int) and abs(node.value) < 1_000_000:
            if self._is_target():
                self.applied = True
                return ast.copy_location(
                    ast.Constant(value=node.value + 1), node
                )
        return node


def _sym(op: ast.AST) -> str:
    return _sym_name(type(op).__name__)


def _sym_name(name: str) -> str:
    symbols = {
        "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=",
        "Eq": "==", "NotEq": "!=", "Add": "+", "Sub": "-",
        "Mult": "*", "Div": "/", "FloorDiv": "//", "Mod": "%",
        "And": "and", "Or": "or",
    }
    return symbols.get(name, name)


def _mutant_cache_key(
    mutated_source: str,
    test_source: str,
    extra_files: dict[str, str] | None,
    node_ids: tuple[str, ...] | None = None,
) -> str:
    """Calcola la chiave di cache per la coppia (mutante, test).

    La chiave include anche gli `extra_files`, cosi' una cache
    condivisa tra run diversi non confonde esiti calcolati con
    dipendenze diverse. Include anche `node_ids` (i test selezionati
    via `CoverageMap`, se presenti): un mutante ucciso eseguendo solo
    un sottoinsieme di test non e' lo stesso esito di un mutante
    ucciso dall'intera suite, quindi le due chiavi devono differire
    (altrimenti si rischiano hit di cache sbagliati).
    """

    payload = (
        mutated_source
        + "\0"
        + test_source
        + "\0"
        + str(sorted((extra_files or {}).items()))
        + "\0"
        + str(node_ids or ())
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _site_priority(
    lineno: int,
    description: str,
    target_lines: set[int] | None,
) -> tuple[int, int]:
    """Priorita' euristica di un sito mutabile (piu' basso = prima).

    Ordine: righe del diff, poi confronti/condizioni/boolean (dove
    vivono i bug di boundary), poi costanti (off-by-one), poi il
    resto. Ispirato alla ricerca su predictive mutant selection:
    a parita' di budget, prima i mutanti con piu' probabilita' di
    rivelare test deboli.
    """

    on_target = 0 if (target_lines and lineno in target_lines) else 1

    if "confronto" in description or "negazione" in description:
        category = 0
    elif "booleano" in description:
        category = 1
    elif "costante" in description:
        category = 2
    elif "aritmetico" in description:
        category = 3
    else:  # slice, chiamate, return anticipato
        category = 4

    return (on_target, category)


class MutationEngine:
    """Genera mutanti ed esegue i test contro ciascuno."""

    def __init__(
        self,
        sandbox: SandboxRunner | None = None,
        max_mutants: int = 40,
        cache: dict[str, bool] | None = None,
    ) -> None:
        self.sandbox = sandbox or SandboxRunner()
        self.max_mutants = max_mutants
        # Cache mutante -> esito (True = ucciso). Se non fornita da
        # fuori (per condividerla tra piu' MutationEngine), se ne
        # crea una interna vuota.
        self.cache: dict[str, bool] = cache if cache is not None else {}
        self.cache_hits: int = 0

    def generate_mutants(
        self,
        source: str,
        target_lines: set[int] | None = None,
    ) -> list[tuple[Mutant, str]]:
        """Ritorna coppie (mutante, sorgente_mutato).

        Se `target_lines` e' fornito, genera solo i mutanti il cui
        `lineno` appartiene all'insieme (mutazione guidata dal diff:
        si mutano solo le righe effettivamente cambiate).
        """

        tree = ast.parse(source)

        collector = _SiteCollector()
        collector.visit(tree)

        source_lines = source.splitlines()
        mutants: list[tuple[Mutant, str]] = []

        # Selezione euristica: ordina i siti per priorita' (righe
        # target, poi categorie ad alto segnale) prima del budget.
        ordered_sites = sorted(
            enumerate(collector.sites),
            key=lambda item: _site_priority(
                item[1][0], item[1][1], target_lines
            ),
        )

        for index, (lineno, description) in ordered_sites:
            if len(mutants) >= self.max_mutants:
                break

            if target_lines is not None and lineno not in target_lines:
                continue

            mutator = _Mutator(target_index=index)
            mutated_tree = mutator.visit(copy.deepcopy(tree))

            if not mutator.applied:
                continue

            ast.fix_missing_locations(mutated_tree)

            try:
                mutated_source = ast.unparse(mutated_tree)
            except Exception:
                continue

            original_snippet = ""
            if 0 < lineno <= len(source_lines):
                original_snippet = source_lines[lineno - 1].strip()

            mutants.append(
                (
                    Mutant(
                        mutant_id=len(mutants) + 1,
                        lineno=lineno,
                        description=description,
                        original_snippet=original_snippet,
                    ),
                    mutated_source,
                )
            )

        return mutants

    def run(
        self,
        source: str,
        module_name: str,
        test_source: str,
        test_file_name: str = "test_target.py",
        target_lines: set[int] | None = None,
        extra_files: dict[str, str] | None = None,
        coverage_map: CoverageMap | None = None,
    ) -> MutationReport:
        """Esegue mutation testing: per ogni mutante, i test devono fallire.

        `target_lines`, se fornito, limita la mutazione alle sole righe
        indicate (mutazione guidata dal diff).

        `coverage_map`, se fornito e `available`, abilita il PER-TEST
        COVERAGE (Fase A della roadmap): per ogni mutante si eseguono
        solo i test che coprono `mutant.lineno` (via `CoverageMap`,
        costruita a monte con `build_coverage_map`) invece dell'intera
        suite, riducendo drasticamente il tempo del run. Se nessun
        test copre la riga mutata, il mutante e' banalmente
        "sopravvissuto" (nessun test puo' rilevarlo) e non si esegue
        alcun test in sandbox. Se `coverage_map` e' `None` o non
        `available`, il comportamento resta identico a prima: si
        esegue sempre l'intera suite per ogni mutante (retrocompatibile).

        Ogni esito (ucciso/sopravvissuto) e' memorizzato in `self.cache`
        sotto una chiave derivata da sorgente mutato, test, extra_files
        e i node_ids dei test selezionati via `coverage_map` (se
        presenti): se lo stesso mutante e' gia' in cache, la sandbox
        non viene rieseguita e l'esito viene riletto direttamente
        (contato in `self.cache_hits`).
        """

        self.cache_hits = 0

        mutants = self.generate_mutants(source, target_lines=target_lines)

        if not mutants:
            return MutationReport(
                skipped_reason="Nessun sito mutabile trovato nel sorgente."
            )

        use_coverage = coverage_map is not None and coverage_map.available

        killed = 0
        surviving: list[MutantResult] = []

        for mutant, mutated_source in mutants:
            node_ids: tuple[str, ...] | None = None

            if use_coverage:
                assert coverage_map is not None
                covering_tests = coverage_map.tests_for_line(mutant.lineno)

                if not covering_tests:
                    surviving.append(
                        MutantResult(
                            mutant=mutant,
                            killed=False,
                            detail="nessun test copre la riga",
                        )
                    )
                    continue

                node_ids = tuple(sorted(covering_tests))

            cache_key = _mutant_cache_key(
                mutated_source, test_source, extra_files, node_ids=node_ids
            )

            if cache_key in self.cache:
                self.cache_hits += 1
                mutant_killed = self.cache[cache_key]
            else:
                run_kwargs: dict[str, object] = {
                    "files": {
                        f"{module_name}.py": mutated_source,
                        test_file_name: test_source,
                        **(extra_files or {}),
                    },
                }

                if node_ids is not None:
                    run_kwargs["extra_args"] = [
                        "-q",
                        "--no-header",
                        "-p",
                        "no:cacheprovider",
                        *node_ids,
                    ]

                result = self.sandbox.run_pytest(**run_kwargs)

                # Test falliti (exit != 0) o timeout = mutante rilevato.
                mutant_killed = not result.ok
                self.cache[cache_key] = mutant_killed

            if mutant_killed:
                killed += 1
            else:
                surviving.append(
                    MutantResult(
                        mutant=mutant,
                        killed=False,
                        detail=(
                            "I test passano anche con questa mutazione: "
                            "il comportamento non e' verificato."
                        ),
                    )
                )

        total = len(mutants)

        return MutationReport(
            total_mutants=total,
            killed=killed,
            survived=total - killed,
            mutation_score=round(killed / total, 3) if total else 0.0,
            surviving_mutants=surviving,
        )
