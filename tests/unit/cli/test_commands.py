from typer.testing import CliRunner

from assist.cli.main import app

runner = CliRunner()


def test_help_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0

    assert "generate" in result.output
    assert "review" in result.output