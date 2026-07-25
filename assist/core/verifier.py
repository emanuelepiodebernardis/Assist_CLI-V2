import ast
import re

from assist.schemas.models import (
    AgentOutput,
    VerificationResult,
)

PLACEHOLDER_PATTERNS: list[str] = [
    r"TODO",
    r"FIXME",
    r"<insert_here>",
]


PYTHON_OUTPUT_TASKS: set[str] = {
    "generate",
    "refactor",
}


REFACTOR_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    re.DOTALL,
)


class GlobalVerifier:

    def check(
        self,
        output: AgentOutput,
    ) -> VerificationResult:

        warnings: list[str] = []
        fatal_issues: list[str] = []

        syntax_ok = self._check_python_syntax(
            output.content,
            output.task_type,
            fatal_issues,
        )

        format_ok = self._check_not_empty(
            output.content,
            fatal_issues,
        )

        self._check_placeholders(
            output.content,
            warnings,
        )

        coherent_with_task = True

        passed = (
            syntax_ok
            and format_ok
            and len(fatal_issues) == 0
        )

        return VerificationResult(
            passed=passed,
            syntax_ok=syntax_ok,
            coherent_with_task=coherent_with_task,
            format_ok=format_ok,
            warnings=warnings,
            fatal_issues=fatal_issues,
        )

    def _check_python_syntax(
        self,
        content: str,
        task_type: str,
        fatal_issues: list[str],
    ) -> bool:

        if task_type not in PYTHON_OUTPUT_TASKS:
            return True

        if task_type == "refactor":
            code = self._extract_refactor_code(
                content,
                fatal_issues,
            )

            if code is None:
                return False

        else:
            code = content

        try:
            ast.parse(code)
            return True

        except SyntaxError as error:
            fatal_issues.append(
                f"Invalid Python syntax: {error}"
            )
            return False

    def _extract_refactor_code(
        self,
        content: str,
        fatal_issues: list[str],
    ) -> str | None:

        match = REFACTOR_CODE_BLOCK_PATTERN.search(
            content
        )

        if match is None:
            fatal_issues.append(
                "Refactor output missing fenced code block. "
                "Expected ```python ... ``` inside "
                "'## Codice refactorizzato' section."
            )
            return None

        return match.group(1)

    def _check_not_empty(
        self,
        content: str,
        fatal_issues: list[str],
    ) -> bool:

        if not content.strip():
            fatal_issues.append(
                "Output is empty"
            )
            return False

        return True

    def _check_placeholders(
        self,
        content: str,
        warnings: list[str],
    ) -> None:

        for pattern in PLACEHOLDER_PATTERNS:

            if re.search(pattern, content):
                warnings.append(
                    f"Placeholder detected: {pattern}"
                )