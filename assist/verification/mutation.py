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
        self.generic_visit(node)

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
) -> str:
    """Calcola la chiave di cache per la coppia (mutante, test).

    La chiave include anche gli `extra_files`, cosi' una cache
    condivisa tra run diversi non confonde esiti calcolati con
    dipendenze diverse.
    """

    payload = (
        mutated_source
        + "\0"
        + test_source
        + "\0"
        + str(sorted((extra_files or {}).items()))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

        for index, (lineno, description) in enumerate(collector.sites):
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
    ) -> MutationReport:
        """Esegue mutation testing: per ogni mutante, i test devono fallire.

        `target_lines`, se fornito, limita la mutazione alle sole righe
        indicate (mutazione guidata dal diff).

        Ogni esito (ucciso/sopravvissuto) e' memorizzato in `self.cache`
        sotto una chiave derivata da sorgente mutato, test ed
        extra_files: se lo stesso mutante e' gia' in cache, la sandbox
        non viene rieseguita e l'esito viene riletto direttamente
        (contato in `self.cache_hits`).
        """

        self.cache_hits = 0

        mutants = self.generate_mutants(source, target_lines=target_lines)

        if not mutants:
            return MutationReport(
                skipped_reason="Nessun sito mutabile trovato nel sorgente."
            )

        killed = 0
        surviving: list[MutantResult] = []

        for mutant, mutated_source in mutants:
            cache_key = _mutant_cache_key(mutated_source, test_source, extra_files)

            if cache_key in self.cache:
                self.cache_hits += 1
                mutant_killed = self.cache[cache_key]
            else:
                result = self.sandbox.run_pytest(
                    files={
                        f"{module_name}.py": mutated_source,
                        test_file_name: test_source,
                        **(extra_files or {}),
                    },
                )

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
