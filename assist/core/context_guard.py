class ContextGuard:
    MAX_CHARS = 12000

    @classmethod
    def validate(
        cls,
        content: str,
    ) -> str:

        if len(content) <= cls.MAX_CHARS:
            return content

        truncated = content[: cls.MAX_CHARS]

        return (
            truncated
            + "\n\n...[TRUNCATED DUE TO SIZE LIMIT]..."
        )