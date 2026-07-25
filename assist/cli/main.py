import typer

from assist.cli.commands import (
    diff_command,
    explain_command,
    generate_command,
    install_hooks_command,
    refactor_command,
    repo_command,
    review_command,
    test_command,
    verify_command,
)

app = typer.Typer(
    help="Assist CLI — Modular AI Coding Assistant",
    no_args_is_help=True,
)

app.command(name="generate")(generate_command)
app.command(name="review")(review_command)
app.command(name="refactor")(refactor_command)
app.command(name="explain")(explain_command)
app.command(name="test")(test_command)
app.command(name="diff")(diff_command)
app.command(name="repo")(repo_command)
app.command(name="verify")(verify_command)
app.command(name="install-hooks")(install_hooks_command)


if __name__ == "__main__":
    app()