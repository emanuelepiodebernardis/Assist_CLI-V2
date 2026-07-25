from assist.core.verifier import GlobalVerifier
from assist.schemas.models import AgentOutput


def test_verifier_accepts_valid_python():

    verifier = GlobalVerifier()

    output = AgentOutput(
        content="print('hello')",
        agent_name="GeneratorAgent",
        task_type="generate",
        quality_score=0.95,
        iterations_used=1,
    )

    result = verifier.check(output)

    assert result.passed is True
    assert result.syntax_ok is True


def test_verifier_rejects_invalid_python():

    verifier = GlobalVerifier()

    output = AgentOutput(
        content="def broken(:",
        agent_name="GeneratorAgent",
        task_type="generate",
        quality_score=0.95,
        iterations_used=1,
    )

    result = verifier.check(output)

    assert result.passed is False
    assert result.syntax_ok is False
    assert any(
        "Invalid Python syntax" in issue
        for issue in result.fatal_issues
    )


def test_verifier_accepts_markdown_review():

    verifier = GlobalVerifier()

    markdown_review = (
        "## Sommario\n\n"
        "Il file presenta due problemi critici.\n\n"
        "## Problemi critici\n\n"
        "Nessuno.\n\n"
        "## Problemi significativi\n\n"
        "Nessuno."
    )

    output = AgentOutput(
        content=markdown_review,
        agent_name="ReviewerAgent",
        task_type="review",
        quality_score=0.95,
        iterations_used=1,
    )

    result = verifier.check(output)

    assert result.passed is True
    assert result.syntax_ok is True


def test_verifier_detects_placeholders():

    verifier = GlobalVerifier()

    output = AgentOutput(
        content="# TODO implement this",
        agent_name="ReviewerAgent",
        task_type="review",
        quality_score=0.95,
        iterations_used=1,
    )

    result = verifier.check(output)

    assert len(result.warnings) > 0