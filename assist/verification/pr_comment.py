"""Rendering del report di verifica come commento PR GitHub.

Traduce l'output della pipeline di verifica (uno o piu' file) in un
singolo blocco di testo markdown GitHub-flavored, pensato per essere
postato o aggiornato come commento su una pull request.

Principio: nessuna dipendenza da rich o typer, solo stringhe — cosi'
il modulo puo' essere riusato sia dalla CLI (--format pr-comment) sia
da uno script Python invocato dalla GitHub Action.
"""

from assist.verification.evidence import (
    EvidenceBundle,
    MutationReport,
    SandboxResult,
    Verdict,
    VerificationOutput,
)

_MAX_COMMENT_CHARS = 60_000
_MAX_SURVIVING_MUTANTS_SHOWN = 5
_MAX_SANDBOX_LOG_CHARS = 1_500
_MAX_SANDBOX_LOG_LINES = 30
_MAX_MUTANT_DETAIL_ROWS = 25

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
    mutanti sopravvissuti, l'eventuale fix validato in sandbox e due
    sotto-sezioni annidate con le evidenze grezze (log di esecuzione
    e dettaglio completo dei mutanti sopravvissuti).

    Il risultato viene troncato a circa 60.000 caratteri per
    rispettare il limite di GitHub sui commenti (65.536 caratteri),
    mantenendo sempre header e tabella intatti.
    """
    header = _render_header(outputs)
    table = _render_table(outputs)
    file_sections = [
        _build_file_section(path, output)
        for path, output in outputs
        if output.verdict.status != "pass"
    ]
    details_sections = [_assemble_file_section(fs) for fs in file_sections]

    full = "\n\n".join(
        part
        for part in [header, table, *details_sections, _FOOTER]
        if part
    )

    if len(full) <= _MAX_COMMENT_CHARS:
        return full

    return _render_truncated(header, table, file_sections)


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
        "| File | Verdetto | Mutation score | Test | Fix |",
        "|---|---|---|---|---|",
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
        fix_cell = _render_fix_cell(verdict)

        lines.append(
            f"| `{path}` | {verdetto_cell} | {mutation_cell} | "
            f"{test_cell} | {fix_cell} |"
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


def _render_fix_cell(verdict: Verdict) -> str:
    """Riassume lo stato del fix: validato, proposto oppure assente."""
    if verdict.fix_validated:
        return "✅ validato"
    if verdict.proposed_fix:
        return "proposto"
    return "—"


def _build_file_section(
    path: str,
    output: VerificationOutput,
) -> dict[str, str]:
    """Prepara i tre blocchi che compongono la sezione di un file.

    Restituisce un dizionario con "body" (apertura <details>, motivi,
    mutanti in breve, fix — senza tag di chiusura), "log_section"
    (sotto-sezione annidata coi log sandbox, eventualmente vuota) e
    "mutant_section" (sotto-sezione annidata col dettaglio completo
    dei mutanti sopravvissuti, eventualmente vuota).
    """
    return {
        "body": _render_details_body(path, output),
        "log_section": _render_sandbox_log_section(output.evidence),
        "mutant_section": _render_mutant_detail_section(
            output.evidence.mutation
        ),
    }


def _assemble_file_section(
    file_section: dict[str, str],
    include_log: bool = True,
    include_mutants: bool = True,
) -> str:
    """Ricompone una sezione file completa a partire dai suoi blocchi."""
    parts = [file_section["body"]]

    if include_log and file_section["log_section"]:
        parts.append(file_section["log_section"])

    if include_mutants and file_section["mutant_section"]:
        parts.append(file_section["mutant_section"])

    parts.append("</details>")

    return "\n\n".join(parts)


def _render_details_body(
    path: str,
    output: VerificationOutput,
) -> str:
    """Corpo della sezione <details> di un file non pass.

    Include apertura del tag, motivi del verdetto, l'elenco breve dei
    mutanti sopravvissuti (i primi pochi) e l'eventuale fix validato.
    Non include il tag di chiusura </details>, aggiunto in seguito
    da _assemble_file_section dopo le sotto-sezioni annidate.
    """
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

    return "\n".join(lines).rstrip("\n")


def _render_sandbox_log_section(evidence: EvidenceBundle) -> str:
    """Sotto-sezione annidata coi log grezzi delle esecuzioni sandbox.

    Per ogni run presente (baseline e boundary) mostra etichetta,
    esito e il failure_summary oppure, se assente, le ultime righe di
    stdout+stderr della sandbox. Se non c'e' alcun run, restituisce
    stringa vuota cosi' la sezione non viene mostrata.
    """
    blocks = []

    for run in (evidence.baseline_tests, evidence.boundary_tests):
        if run is None:
            continue

        esito = "✅ passato" if run.passed else "❌ fallito"
        blocks.append(f"**{run.label}** — {esito}")

        content = run.failure_summary.strip()
        if not content:
            content = _tail_sandbox_output(run.sandbox)
        content = content[:_MAX_SANDBOX_LOG_CHARS]

        blocks.append(f"```\n{content}\n```")

    if not blocks:
        return ""

    lines = [
        "<details><summary>📋 Log di esecuzione (sandbox)</summary>",
        "",
        *blocks,
        "</details>",
    ]

    return "\n".join(lines)


def _tail_sandbox_output(sandbox: SandboxResult) -> str:
    """Ultime righe di stdout+stderr della sandbox, o un placeholder."""
    combined = (sandbox.stdout + "\n" + sandbox.stderr).strip()

    if not combined:
        return "(nessun output)"

    lines = combined.splitlines()
    return "\n".join(lines[-_MAX_SANDBOX_LOG_LINES:])


def _render_mutant_detail_section(
    mutation: MutationReport | None,
) -> str:
    """Sotto-sezione annidata con la tabella di tutti i mutanti vivi.

    A differenza dell'elenco breve nel corpo principale, mostra tutti
    i mutanti sopravvissuti (fino a _MAX_MUTANT_DETAIL_ROWS righe di
    tabella, poi una nota col conteggio dei rimanenti).
    """
    if mutation is None or not mutation.surviving_mutants:
        return ""

    mutants = mutation.surviving_mutants
    shown = mutants[:_MAX_MUTANT_DETAIL_ROWS]

    lines = [
        "<details><summary>🧬 Dettaglio mutanti sopravvissuti</summary>",
        "",
        "| Riga | Mutazione | Codice originale | Perché conta |",
        "|---|---|---|---|",
    ]

    for mutant_result in shown:
        mutant = mutant_result.mutant
        snippet = mutant.original_snippet or mutant.mutated_snippet
        perche = mutant_result.detail or "—"
        lines.append(
            f"| {mutant.lineno} | {_escape_cell(mutant.description)} | "
            f"`{_escape_cell(snippet)}` | {_escape_cell(perche)} |"
        )

    remaining = len(mutants) - len(shown)
    if remaining > 0:
        lines.append("")
        lines.append(f"... e altri {remaining}")

    lines.append("")
    lines.append("</details>")

    return "\n".join(lines)


def _escape_cell(text: str) -> str:
    """Rende un testo sicuro da inserire in una cella di tabella md."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _render_truncated(
    header: str,
    table: str,
    file_sections: list[dict[str, str]],
) -> str:
    """Ricostruisce il commento troncando le sezioni di dettaglio.

    Header e tabella restano sempre completi. Tra le sezioni annidate
    dei file non-pass, le prime a essere sacrificate sono i log di
    esecuzione sandbox, poi il dettaglio completo dei mutanti; solo
    se anche cosi' non si rientra nel budget si passa al vecchio
    troncamento carattere-per-carattere del corpo di ogni sezione.
    """
    reserved = (
        len(header) + len(table) + len(_FOOTER)
        + len(_TRUNCATION_NOTE) + 8
    )
    budget = max(_MAX_COMMENT_CHARS - reserved, 0)

    kept: list[str] = []
    for include_log, include_mutants in (
        (True, True),
        (False, True),
        (False, False),
    ):
        sections = [
            _assemble_file_section(
                fs, include_log=include_log, include_mutants=include_mutants
            )
            for fs in file_sections
        ]
        if sum(len(section) for section in sections) <= budget:
            kept = sections
            break
    else:
        base_sections = [
            _assemble_file_section(
                fs, include_log=False, include_mutants=False
            )
            for fs in file_sections
        ]
        kept = _fit_sections_within_budget(base_sections, budget)

    parts = [header, table, *kept, _TRUNCATION_NOTE, _FOOTER]
    result = "\n\n".join(part for part in parts if part)

    if len(result) > _MAX_COMMENT_CHARS:
        cutoff = _MAX_COMMENT_CHARS - len(_TRUNCATION_NOTE) - 20
        result = result[:cutoff] + _TRUNCATION_NOTE

    return result


def _fit_sections_within_budget(
    sections: list[str],
    budget: int,
) -> list[str]:
    """Include le sezioni finche' rientrano nel budget di caratteri.

    L'ultima sezione che non entra per intero viene troncata a livello
    di carattere, con una nota "(troncato)" in coda.
    """
    kept: list[str] = []
    used = 0

    for section in sections:
        if used + len(section) <= budget:
            kept.append(section)
            used += len(section)
            continue

        remaining = budget - used
        if remaining > 200:
            kept.append(section[:remaining] + "\n... (troncato)")
            used = budget

        break

    return kept
