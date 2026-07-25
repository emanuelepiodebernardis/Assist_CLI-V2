import json
import re

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from assist.schemas.models import FinalOutput

CODE_BLOCK_PATTERN = re.compile(
    r"```(\w+)?\s*\n(.*?)```",
    re.DOTALL,
)


PURE_CODE_TASKS: set[str] = {
    "generate",
    "test",
}


MIXED_CODE_TASKS: set[str] = {
    "refactor",
}


PROSE_TASKS: set[str] = {
    "review",
    "explain",
    "diff",
    "repo",
}


class OutputFormatter:

    def format(
        self,
        output: FinalOutput,
        format_type: str = "terminal",
    ):

        if format_type == "json":
            return self.format_json(output)

        if format_type == "markdown":
            return self.format_markdown(output)

        return self.format_terminal(output)

    def format_terminal(
        self,
        output: FinalOutput,
    ):

        verification = output.verification

        header = Panel.fit(
            (
                f"[bold cyan]ASSIST REVIEW RESULT[/bold cyan]\n\n"
                f"[bold]Agent:[/bold] {output.agent_name}\n"
                f"[bold]Task:[/bold] {output.task_type}\n"
                f"[bold]Quality Score:[/bold] "
                f"{output.quality_score:.2f}\n"
                f"[bold]Iterations:[/bold] "
                f"{output.iterations_used}"
            ),
            border_style="cyan",
        )

        verification_table = Table(
            title="Verification Status",
            show_header=True,
            header_style="bold magenta",
        )

        verification_table.add_column(
            "Check",
            style="bold",
        )

        verification_table.add_column(
            "Status",
        )

        verification_table.add_row(
            "Passed",
            "PASS" if verification.passed else "FAIL",
        )

        verification_table.add_row(
            "Syntax",
            "PASS" if verification.syntax_ok else "FAIL",
        )

        verification_table.add_row(
            "Format",
            "PASS" if verification.format_ok else "FAIL",
        )

        verification_table.add_row(
            "Coherence",
            (
                "PASS"
                if verification.coherent_with_task
                else "FAIL"
            ),
        )

        body_panel = self._render_body(
            output
        )

        return Group(
            header,
            verification_table,
            body_panel,
        )

    def _render_body(
        self,
        output: FinalOutput,
    ) -> Panel:

        task_type = output.task_type

        title = self._panel_title_for(
            task_type
        )

        if task_type in PURE_CODE_TASKS:
            body = self._render_pure_code(
                output.raw_content
            )

        elif task_type in MIXED_CODE_TASKS:
            body = self._render_mixed_content(
                output.raw_content
            )

        else:
            body = Markdown(
                output.raw_content
            )

        return Panel(
            body,
            title=title,
            border_style="green",
        )

    @staticmethod
    def _panel_title_for(
        task_type: str,
    ) -> str:

        titles = {
            "review": "Review",
            "refactor": "Refactor",
            "generate": "Generated Code",
            "explain": "Explanation",
            "test": "Generated Tests",
            "diff": "Diff Review",
            "repo": "Repository Overview",
        }

        return titles.get(
            task_type,
            "Output",
        )

    @staticmethod
    def _render_pure_code(
        content: str,
    ) -> Syntax:

        code = OutputFormatter._strip_code_fences(
            content
        )

        return Syntax(
            code,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )

    @staticmethod
    def _strip_code_fences(
        content: str,
    ) -> str:

        match = CODE_BLOCK_PATTERN.search(
            content
        )

        if match is not None:
            return match.group(2).rstrip()

        return content.strip()

    @staticmethod
    def _render_mixed_content(
        content: str,
    ) -> Group:

        renderables: list[RenderableType] = []

        cursor = 0

        for match in CODE_BLOCK_PATTERN.finditer(
            content
        ):

            prose_before = content[
                cursor : match.start()
            ].strip()

            if prose_before:
                renderables.append(
                    Markdown(prose_before)
                )

            language = (
                match.group(1)
                or "python"
            )

            code = match.group(2).rstrip()

            renderables.append(
                Syntax(
                    code,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=False,
                )
            )

            cursor = match.end()

        remaining_prose = content[cursor:].strip()

        if remaining_prose:
            renderables.append(
                Markdown(remaining_prose)
            )

        if not renderables:
            renderables.append(
                Markdown(content)
            )

        return Group(*renderables)

    def format_markdown(
        self,
        output: FinalOutput,
    ) -> str:

        verification = output.verification

        return f"""# ASSIST Review Result

## Metadata
- Agent: {output.agent_name}
- Task: {output.task_type}
- Quality score: {output.quality_score:.2f}
- Iterations used: {output.iterations_used}

## Verification
- Passed: {verification.passed}
- Syntax OK: {verification.syntax_ok}
- Coherent with task: {verification.coherent_with_task}
- Format OK: {verification.format_ok}

### Warnings
{self._format_list(verification.warnings)}

### Fatal issues
{self._format_list(verification.fatal_issues)}

## Review
{output.raw_content}
"""

    def format_json(
        self,
        output: FinalOutput,
    ) -> str:

        return json.dumps(
            output.model_dump(),
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def _format_list(items: list[str]) -> str:

        if not items:
            return "- Nessun elemento"

        return "\n".join(
            f"- {item}"
            for item in items
        )