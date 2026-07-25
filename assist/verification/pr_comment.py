"""Rendering del report di verifica come commento PR GitHub.

Traduce l'output della pipeline di verifica (uno o piu' file) in un
singolo blocco di testo markdown GitHub-flavored, pensato per essere
postato o aggiornato come commento su una pull request.

Principio: nessuna dipendenza da rich o typer, solo stringhe — cosi'
il modulo puo' essere riusato sia dalla CLI (--format pr-comment) sia
da uno script Python invocato dalla GitHub Action.
"""

from assist.verification.evidence import EvidenceBundle, VerificationOutput

_MAX_COMMENT_CHARS = 60_000
_MAX_SURVIVING_MUTANTS_SHOWN = 5

_STATUS_BADGE = {"pass": "✅", "warn": "⚠️", "fail": "❌"}

_TRUNCATION_NOTE = "\n\n> ⚠️ (output troncato)\n"

_FOOTER = (
    "<sub>Generato da Assist CLI · verdetti decisi da evidenze "
    "deterministiche (sandbox + mutation testing)</sub>"
)


def render_pr_comment(
    outputs: list[tuple[str, VerificationOutput]],
) -> str:
    """Rende il report di verifica come commento markdown per PR.

    Ogni tupla e' (percorso_file, output_di_verifica). Produce un
    header riassuntivo, una tabella con un verdetto per file e, per
    ogni file non "pass", una sezione dettagliata con i motivi, i
    mutanti sopravvissuti e l'eventuale fix validato in sandbox.

    Il risultato viene troncato a circa 60.000 caratteri per
    rispettare il limite di GitHub sui commenti (65.536 caratteri),
    mantenendo sempre header e tabella intatti.
    """
    header = _render_header(outputs)
    table = _render_table(outputs)
    details_sections = [
        _render_details(path, output)
        for path, output in outputs
        if output.verdict.status != "pass"
    ]

    full = "\n\n".join(
        part
        for part in [header, table, *details_sections, _FOOTER]
        if part
    )

    if len(full) <= _MAX_COMMENT_CHARS:
        return full

    return _render_truncated(header, table, details_sections)


def _render_header(
    outputs: list[tuple[str, VerificationOutput]],
) -> str:
    """Costruisce l'header con il conteggio pass/warn/fail."""
    counts = {"pass": 0, "warn": 0, "fail": 0}

    for _, output in outputs:
        status = output.verdict.status
        counts[status] = counts.get(status, 0) + 1

    total = len(outputs)
    plural = "o" if total == 1 else "i"

    summary = (
        f"**{total} file verificat{plural}** — "
        f"✅ {counts['pass']} pass · "
        f"⚠️ {counts['warn']} warn · "
        f"❌ {counts['fail']} fail"
    )

    return "## 🔬 Assist Proof Engine\n\n" + summary


def _render_table(
    outputs: list[tuple[str, VerificationOutput]],
) -> str:
    """Costruisce la tabella riassuntiva, una riga per file."""
    lines = [
        "| File | Verdetto | Mutation score | Test |",
        "|---|---|---|---|",
    ]

    for path, output in outputs:
        verdict = output.verdict
        badge = _STATUS_BADGE.get(verdict.status, "")
        verdetto_cell = f"{badge} {verdict.status.upper()}"

        mutation_cell = (
            f"{verdict.mutation_score:.0%}"
            if verdict.mutation_score is not None
            else "n/a"
        )

        test_cell = _render_test_cell(output.evidence)

        lines.append(
            f"| `{path}` | {verdetto_cell} | {mutation_cell} | "
            f"{test_cell} |"
        )

    return "\n".join(lines)


def _render_test_cell(evidence: EvidenceBundle) -> str:
    """Riassume l'esito dei test, es. '3 ok' oppure '2 falliti'."""
    collected = 0
    failed = 0
    any_run = False

    for run in (evidence.baseline_tests, evidence.boundary_tests):
        if run is None:
            continue
        any_run = True
        collected += run.tests_collected
        failed += run.tests_failed

    if not any_run:
        return "n/a"

    if failed > 0:
        plural = "o" if failed == 1 else "i"
        return f"{failed} fallit{plural}"

    return f"{collected} ok"


def _render_details(
    path: str,
    output: VerificationOutput,
) -> str:
    """Sezione <details> con motivi, mutanti e fix per un file non pass."""
    verdict = output.verdict
    badge = _STATUS_BADGE.get(verdict.status, "")

    lines = [
        f"<details><summary>{badge} <strong>{verdict.status.upper()}"
        f"</strong> — <code>{path}</code></summary>",
        "",
    ]

    if verdict.reasons:
        lines.append("**Motivi:**")
        lines.extend(f"- {reason}" for reason in verdict.reasons)
        lines.append("")

    mutants = []
    if output.evidence.mutation is not None:
        mutants = output.evidence.mutation.surviving_mutants[
            :_MAX_SURVIVING_MUTANTS_SHOWN
        ]

    if mutants:
        lines.append("**Mutanti sopravvissuti:**")
        for mutant_result in mutants:
            mutant = mutant_result.mutant
            snippet = mutant.original_snippet or mutant.mutated_snippet
            lines.append(
                f"- riga {mutant.lineno}: {mutant.description} — "
                f"`{snippet}`"
            )
        lines.append("")

    if verdict.fix_validated and verdict.proposed_fix:
        lines.append("Fix validato in sandbox ✅")
        lines.append("")
        lines.append("```python")
        lines.append(verdict.proposed_fix)
        lines.append("```")
        lines.append("")

    lines.append("</details>")

    return "\n".join(lines)


def _render_truncated(
    header: str,
    table: str,
    details_sections: list[str],
) -> str:
    """Ricostruisce il commento troncando le sezioni di dettaglio.

    Header e tabella restano sempre completi; le sezioni <details>
    vengono incluse finche' rientrano nel budget di caratteri residuo,
    poi viene aggiunta una nota di troncamento.
    """
    reserved = (
        len(header) + len(table) + len(_FOOTER)
        + len(_TRUNCATION_NOTE) + 8
    )
    budget = max(_MAX_COMMENT_CHARS - reserved, 0)

    kept: list[str] = []
    used = 0

    for section in details_sections:
        if used + len(section) <= budget:
            kept.append(section)
            used += len(section)
            continue

        remaining = budget - used
        if remaining > 200:
            kept.append(section[:remaining] + "\n... (troncato)")
            used = budget

        break

    parts = [header, table, *kept, _TRUNCATION_NOTE, _FOOTER]
    result = "\n\n".join(part for part in parts if part)

    if len(result) > _MAX_COMMENT_CHARS:
        cutoff = _MAX_COMMENT_CHARS - len(_TRUNCATION_NOTE) - 20
        result = result[:cutoff] + _TRUNCATION_NOTE

    return result
