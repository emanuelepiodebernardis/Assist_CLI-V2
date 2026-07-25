from assist.schemas.models import (
    AgentOutput,
    FinalOutput,
    VerificationResult,
)


class ResponseAssembler:
    def build(
        self,
        output: AgentOutput,
        verification: VerificationResult,
    ) -> FinalOutput:

        return FinalOutput(
            raw_content=output.content,
            verification=verification,
            agent_name=output.agent_name,
            task_type=output.task_type,
            quality_score=output.quality_score,
            iterations_used=output.iterations_used,
        )