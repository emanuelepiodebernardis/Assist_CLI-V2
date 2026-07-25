import json

from assist.schemas.models import PromptContext


class PromptContextBuilder:

    def aggregate(
        self,
        options: dict,
        target_file: str = "",
    ) -> PromptContext:

        return PromptContext(
            file_path=(
                target_file
                or options.get("file_path", "")
            ),
            file_metadata=(
                options.get("metadata", {})
                or {}
            ),
            repository_context=(
                options.get("repository_context", {})
                or {}
            ),
            architecture_context=(
                options.get("architecture_context", {})
                or {}
            ),
            semantic_context=(
                options.get("semantic_context", {})
                or {}
            ),
            cross_file_context=(
                options.get("cross_file_context", {})
                or {}
            ),
            risk_context=(
                options.get("risk_context", {})
                or {}
            ),
            code_quality_context=(
                options.get("code_quality_context", {})
                or {}
            ),
        )

    def render(
        self,
        context: PromptContext,
    ) -> str:

        sections: list[str] = []

        if context.file_path:
            sections.append(
                self._section(
                    "Target File",
                    context.file_path,
                )
            )

        if context.file_metadata:
            sections.append(
                self._section(
                    "File Metadata",
                    context.file_metadata,
                )
            )

        if context.repository_context:
            sections.append(
                self._section(
                    "Repository Context",
                    context.repository_context,
                )
            )

        if context.architecture_context:
            sections.append(
                self._section(
                    "Architecture Context",
                    context.architecture_context,
                )
            )

        if context.semantic_context:
            sections.append(
                self._section(
                    "Semantic Context",
                    context.semantic_context,
                )
            )

        if context.cross_file_context:
            sections.append(
                self._section(
                    "Cross File Context",
                    context.cross_file_context,
                )
            )

        if context.risk_context:
            sections.append(
                self._section(
                    "Architectural Risks",
                    context.risk_context,
                )
            )

        if context.code_quality_context:
            sections.append(
                self._section(
                    "Code Quality Context",
                    context.code_quality_context,
                )
            )

        return "\n\n".join(sections)

    def build(
        self,
        options: dict,
    ) -> str:

        context = self.aggregate(options)
        return self.render(context)

    def _section(
        self,
        title: str,
        content: object,
    ) -> str:

        if isinstance(content, (dict, list, tuple)):
            rendered = json.dumps(
                content,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        else:
            rendered = str(content)

        return f"## {title}\n{rendered}"