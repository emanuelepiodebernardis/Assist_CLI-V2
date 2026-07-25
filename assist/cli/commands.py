from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from assist.core.orchestrator import Orchestrator
from assist.core.output_formatter import OutputFormatter
from assist.schemas.models import TaskInput

app = typer.Typer()

console = Console()


def validate_file_exists(
    file_path: str,
) -> None:

    path = Path(file_path)

    if not path.exists():
        raise typer.BadParameter(
            f"File not found: {file_path}"
        )


def validate_directory_exists(
    dir_path: str,
) -> None:

    path = Path(dir_path)

    if not path.exists():
        raise typer.BadParameter(
            f"Directory not found: {dir_path}"
        )

    if not path.is_dir():
        raise typer.BadParameter(
            f"Path is not a directory: {dir_path}"
        )


def _handle_output(
    formatted_output,
    output_format: str,
    output_path: str | None = None,
) -> None:

    if output_path:

        output_file = Path(output_path)

        output_file.write_text(
            str(formatted_output),
            encoding="utf-8",
        )

        typer.echo(
            f"Report saved to: {output_file}"
        )

        return

    if output_format == "terminal":

        console.print(
            formatted_output
        )

    else:

        typer.echo(
            formatted_output
        )


def generate_command(
    file: str,
    prompt: str = "Generate Python code",
    lang: str = "python",
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    task = TaskInput(
        command="generate",
        file_path=file,
        language=lang,
        options={
            "prompt": prompt,
        },
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )


def review_command(
    file: str,
    strict: bool = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    validate_file_exists(file)

    task = TaskInput(
        command="review",
        file_path=file,
        options={
            "strict": strict,
        },
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )


def refactor_command(
    file: str,
    target: str = "readability",
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output_file: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    validate_file_exists(file)

    task = TaskInput(
        command="refactor",
        file_path=file,
        options={
            "target": target,
        },
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = formatter.format(
        result,
        format_type=output_format,
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output_file,
    )


def explain_command(
    file: str,
    depth: str = "brief",
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    validate_file_exists(file)

    task = TaskInput(
        command="explain",
        file_path=file,
        options={
            "depth": depth,
        },
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )


def test_command(
    file: str,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    validate_file_exists(file)

    task = TaskInput(
        command="test",
        file_path=file,
        language="python",
        options={},
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )


def diff_command(
    range: str = typer.Argument(
        "HEAD",
        help="Git range to review (e.g. HEAD, HEAD~3, main..feature)",
    ),
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    task = TaskInput(
        command="diff",
        git_range=range,
        options={},
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )


def repo_command(
    path: str = typer.Argument(
        ".",
        help="Path to the repository to analyze (default: current directory)",
    ),
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="terminal | markdown | json",
        ),
    ] = "terminal",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            help="Save output to file",
        ),
    ] = None,
) -> None:

    validate_directory_exists(path)

    task = TaskInput(
        command="repo",
        repo_path=path,
        options={},
    )

    orchestrator = Orchestrator()

    formatter = OutputFormatter()

    result = orchestrator.run(
        task
    )

    formatted_output = (
        formatter.format(
            result,
            format_type=output_format,
        )
    )

    _handle_output(
        formatted_output=formatted_output,
        output_format=output_format,
        output_path=output,
    )

def verify_command(
    file: Annotated[
        str | None,
        typer.Argument(
            help="File Python da verificare"
        ),
    ] = None,
    tests: Annotated[
        str | None,
        typer.Option(
            "--tests",
            "-t",
            help=(
                "File di test baseline (se omesso: auto-discovery "
                "con convenzioni pytest)"
            ),
        ),
    ] = None,
    diff: Annotated[
        str | None,
        typer.Option(
            "--diff",
            help=(
                "Range git (es. HEAD~1): verifica i file Python "
                "toccati, mutando solo le righe cambiate"
            ),
        ),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="Provider LLM: anthropic | mock",
        ),
    ] = "anthropic",
    report_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Formato report: markdown | pr-comment",
        ),
    ] = "markdown",
    docker: Annotated[
        bool,
        typer.Option(
            "--docker",
            help=(
                "Esegui la sandbox in container Docker "
                "(fallback a processo se Docker manca)"
            ),
        ),
    ] = False,
    audience: Annotated[
        str,
        typer.Option(
            "--audience",
            help=(
                "Pubblico del report: dev | non-dev "
                "(spiegazioni senza gergo tecnico)"
            ),
        ),
    ] = "dev",
    output_path: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Salva il report markdown su file",
        ),
    ] = None,
    certificate_path: Annotated[
        str | None,
        typer.Option(
            "--certificate",
            help=(
                "Esporta il certificato di verifica JSON "
                "(firmato se ASSIST_SIGNING_KEY e' impostata)"
            ),
        ),
    ] = None,
) -> None:
    """Verifica un file con evidenze deterministiche (Proof Engine).

    Esegue: check sintassi, test esistenti in sandbox, generazione
    test boundary (modello fast), mutation testing, verdetto con
    spiegazione e fix (modello strong).
    """

    from assist.core.config import ConfigLoader
    from assist.llm.factory import LLMFactory
    from assist.verification import VerificationPipeline

    if file is None and diff is None:
        raise typer.BadParameter(
            "Indica un file da verificare oppure --diff <range>."
        )

    if file is not None:
        validate_file_exists(file)

    if tests:
        validate_file_exists(tests)

    from assist.verification.repo_config import (
        is_excluded,
        load_repo_config,
    )
    from assist.verification.telemetry import (
        CountingLLM,
        Telemetry,
    )

    if report_format not in ("markdown", "pr-comment"):
        raise typer.BadParameter(
            f"Formato sconosciuto: {report_format}"
        )

    if audience not in ("dev", "non-dev"):
        raise typer.BadParameter(
            f"Audience sconosciuta: {audience} (attesi: dev, non-dev)"
        )

    settings = ConfigLoader().load()

    repo_config = load_repo_config(".")

    merged = repo_config.merged_with(
        mutation_threshold=settings.verify.mutation_threshold,
        sandbox_timeout_seconds=(
            settings.verify.sandbox_timeout_seconds
        ),
        max_mutants=settings.verify.max_mutants,
        generate_boundary_tests=(
            settings.verify.generate_boundary_tests
        ),
        max_fix_iterations=3,
    )

    telemetry = Telemetry()

    pipeline = VerificationPipeline(
        fast_llm=CountingLLM(
            LLMFactory.create_tier("fast", provider=provider),
            on_call=telemetry.count_llm_fast,
        ),
        strong_llm=CountingLLM(
            LLMFactory.create_tier("strong", provider=provider),
            on_call=telemetry.count_llm_strong,
        ),
        sandbox_timeout=merged["sandbox_timeout_seconds"],
        mutation_threshold=merged["mutation_threshold"],
        max_mutants=merged["max_mutants"],
        generate_boundary_tests=merged["generate_boundary_tests"],
        max_fix_iterations=merged["max_fix_iterations"],
        audience=audience,
        use_docker=docker or settings.verify.use_docker,
    )

    targets: list[tuple[str, set[int] | None]] = []

    if diff is not None:
        from assist.core.git_diff_extractor import GitDiffExtractor
        from assist.verification.diff_targets import (
            python_targets_from_diff,
        )

        git_diff = GitDiffExtractor(repo_path=Path(".")).extract(
            range_spec=diff
        )

        diff_targets = python_targets_from_diff(git_diff)

        if not diff_targets:
            typer.echo(
                "Nessun file Python modificato nel range indicato."
            )
            raise typer.Exit(code=0)

        for path, lines in diff_targets.items():
            if not Path(path).exists():
                continue

            if is_excluded(path, repo_config):
                typer.echo(
                    f"Escluso da .assist.yaml: {path}"
                )
                continue

            targets.append((path, lines))
    else:
        if is_excluded(file, repo_config):  # type: ignore[arg-type]
            typer.echo(
                f"File escluso da .assist.yaml: {file}"
            )
            raise typer.Exit(code=0)

        targets.append((file, None))  # type: ignore[arg-type]

    reports: list[str] = []
    outputs = []
    any_fail = False

    with console.status(
        "Verifica in corso (sandbox + mutation testing)..."
    ):
        for target_path, target_lines in targets:
            with telemetry.phase(target_path):
                result = pipeline.run(
                    file_path=target_path,
                    tests_path=tests,
                    target_lines=target_lines,
                )

            reports.append(result.report_markdown)
            outputs.append((target_path, result))

            if result.verdict.status == "fail":
                any_fail = True

    telemetry.stats.mutation_cache_hits = (
        pipeline.mutation_engine.cache_hits
    )
    telemetry.stats.sandbox_runs = pipeline.sandbox.runs

    stats = telemetry.finish()

    if report_format == "pr-comment":
        from assist.verification.pr_comment import (
            render_pr_comment,
        )

        full_report = render_pr_comment(outputs)
    else:
        full_report = "\n\n---\n\n".join(reports)

    if output_path:
        Path(output_path).write_text(
            full_report,
            encoding="utf-8",
        )
        typer.echo(f"Report salvato in {output_path}")
    else:
        console.print(full_report)

    typer.echo(stats.summary_line(), err=True)

    if certificate_path:
        import json

        from assist.verification.certificate import (
            build_certificate,
            certificate_to_json,
            default_signing_key,
        )

        key = default_signing_key()

        certs = [
            build_certificate(
                result,
                source=Path(t_path).read_text(encoding="utf-8"),
                signing_key=key,
            )
            for t_path, result in outputs
        ]

        if len(certs) == 1:
            cert_text = certificate_to_json(certs[0])
        else:
            cert_text = json.dumps(
                [c.model_dump() for c in certs],
                indent=2,
            )

        Path(certificate_path).write_text(
            cert_text,
            encoding="utf-8",
        )

        firmato = "firmato" if key else "NON firmato (ASSIST_SIGNING_KEY assente)"
        typer.echo(
            f"Certificato {firmato}: {certificate_path}",
            err=True,
        )

    if any_fail:
        raise typer.Exit(code=1)


def install_hooks_command(
    pre_commit: Annotated[
        bool,
        typer.Option(
            "--pre-commit",
            help="Installa l'hook git pre-commit (blocca i commit su FAIL)",
        ),
    ] = False,
    claude_code: Annotated[
        bool,
        typer.Option(
            "--claude-code",
            help=(
                "Configura l'hook PostToolUse di Claude Code "
                "(verifica dopo ogni Edit/Write)"
            ),
        ),
    ] = False,
    repo_dir: Annotated[
        str,
        typer.Option(
            "--repo",
            help="Directory del repository (default: corrente)",
        ),
    ] = ".",
) -> None:
    """Installa gli hook di verifica automatica (Proof Engine).

    Senza opzioni mostra le istruzioni. Con --pre-commit e/o
    --claude-code installa gli hook nel repository indicato.
    """

    from assist.verification.hook_install import (
        install_claude_code_hook,
        install_pre_commit,
        render_instructions,
    )

    if not pre_commit and not claude_code:
        console.print(render_instructions())
        return

    if pre_commit:
        try:
            path = install_pre_commit(repo_dir)
        except ValueError as exc:
            typer.echo(f"pre-commit: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        typer.echo(f"Hook pre-commit installato: {path}")

    if claude_code:
        path = install_claude_code_hook(repo_dir)
        typer.echo(f"Hook Claude Code configurato: {path}")
