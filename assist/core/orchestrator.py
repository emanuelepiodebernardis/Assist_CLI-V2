import ast
from pathlib import Path

from assist.agents.diff_reviewer import DiffReviewerAgent
from assist.agents.explainer import ExplainerAgent
from assist.agents.generator import GeneratorAgent
from assist.agents.refactor import RefactorAgent
from assist.agents.repo_agent import RepoAgent
from assist.agents.reviewer import ReviewerAgent
from assist.agents.test_generator import TestGeneratorAgent
from assist.core.architectural_risk_analyzer import (
    ArchitecturalRiskAnalyzer,
)
from assist.core.architecture_analyzer import (
    ArchitectureAnalyzer,
)
from assist.core.assembler import ResponseAssembler
from assist.core.code_quality_analyzer import (
    CodeQualityAnalyzer,
)
from assist.core.context_guard import ContextGuard
from assist.core.cross_file_analyzer import (
    CrossFileAnalyzer,
)
from assist.core.git_diff_extractor import (
    GitDiffExtractor,
)
from assist.core.project_graph import (
    ProjectGraphBuilder,
)
from assist.core.project_scanner import ProjectScanner
from assist.core.registry import Registry
from assist.core.repository_context import (
    RepositoryContextBuilder,
)
from assist.core.repository_health import (
    RepositoryHealthAnalyzer,
)
from assist.core.semantic_analyzer import (
    SemanticAnalyzer,
)
from assist.core.skill_resolver import (
    SkillResolver,
)
from assist.core.verifier import GlobalVerifier
from assist.llm.factory import LLMFactory
from assist.schemas.models import (
    TaskInput,
)
from assist.utils.file_metadata import (
    build_file_metadata,
)
from assist.utils.file_reader import (
    FileReader,
)

MAX_CORRECTIONS_PER_AGENT: dict[str, int] = {
    "ReviewerAgent": 1,
    "GeneratorAgent": 2,
    "RefactorAgent": 2,
    "ExplainerAgent": 1,
    "TestGeneratorAgent": 2,
    "DiffReviewerAgent": 1,
    "RepoAgent": 2,
}


DEFAULT_MAX_CORRECTIONS: int = 1


class Orchestrator:

    def __init__(self) -> None:

        self.registry = Registry()

        self.skill_resolver = SkillResolver()

        self.verifier = GlobalVerifier()

        self.assembler = ResponseAssembler()

    def _build_agent(
        self,
        agent_name: str,
    ):

        llm = LLMFactory.create(
            provider="anthropic",
        )

        agents = {
            "GeneratorAgent": GeneratorAgent,
            "ReviewerAgent": ReviewerAgent,
            "RefactorAgent": RefactorAgent,
            "ExplainerAgent": ExplainerAgent,
            "TestGeneratorAgent": TestGeneratorAgent,
            "DiffReviewerAgent": DiffReviewerAgent,
            "RepoAgent": RepoAgent,
        }

        agent_class = agents[agent_name]

        max_corrections = (
            MAX_CORRECTIONS_PER_AGENT.get(
                agent_name,
                DEFAULT_MAX_CORRECTIONS,
            )
        )

        return agent_class(
            llm=llm,
            max_corrections=max_corrections,
        )

    def run(
        self,
        task: TaskInput,
    ) -> str:

        agent_name, skills = (
            self.registry.resolve(
                task.command
            )
        )

        loaded_skills = (
            self.skill_resolver.load(
                skills
            )
        )

        file_content = ""

        metadata_dump: dict = {}

        repository_context: dict = {}

        semantic_context: dict = {}

        architecture_context: dict = {}

        cross_file_context: dict = {}

        risk_context: dict = {}

        code_quality_context: dict = {}

        impacted_files_content: dict = {}

        if task.git_range:

            extractor = GitDiffExtractor(
                repo_path=Path(".")
            )

            git_diff = extractor.extract(
                range_spec=task.git_range
            )

            file_content = git_diff.raw_diff

            for file_diff in git_diff.files:

                file_path_obj = Path(file_diff.path)

                try:
                    impacted_files_content[
                        file_diff.path
                    ] = file_path_obj.read_text(
                        encoding="utf-8"
                    )

                except (
                    FileNotFoundError,
                    UnicodeDecodeError,
                ):
                    continue

        elif task.file_path:

            raw_content = (
                FileReader.read(
                    task.file_path
                )
            )

            file_content = (
                ContextGuard.validate(
                    raw_content
                )
            )

            metadata = (
                build_file_metadata(
                    task.file_path,
                    raw_content,
                )
            )

            metadata_dump = metadata.model_dump()

            tree = ast.parse(raw_content)

            project_files = (
                ProjectScanner()
                .scan(".")
            )

            repository_context = (
                RepositoryContextBuilder()
                .build(
                    task.file_path,
                    project_files,
                )
            )

            graph = (
                ProjectGraphBuilder()
                .build(".")
            )

            architecture_report = (
                ArchitectureAnalyzer()
                .detect_cycles(
                    graph
                )
            )

            health_report = (
                RepositoryHealthAnalyzer()
                .analyze(
                    graph=graph,
                    cycles=(
                        architecture_report.cycles
                    ),
                )
            )

            risk_report = (
                ArchitecturalRiskAnalyzer()
                .analyze(graph)
            )

            semantic = (
                SemanticAnalyzer()
                .analyze_file(
                    task.file_path
                )
            )

            quality_report = (
                CodeQualityAnalyzer()
                .analyze(
                    semantic=semantic,
                    graph=graph,
                    tree=tree,
                )
            )

            semantic_context = {
                "functions": [
                    function.name
                    for function in (
                        semantic.functions
                    )
                ],
                "classes": [
                    class_.name
                    for class_ in (
                        semantic.classes
                    )
                ],
                "imports": (
                    semantic.imports
                ),
                "calls": (
                    semantic.calls
                ),
            }

            cross_analysis = (
                CrossFileAnalyzer()
                .analyze(project_files)
            )

            cross_file_context = {
                "imports": [
                    {
                        "source": (
                            ref.source_file
                        ),
                        "target": (
                            ref.target_file
                        ),
                        "symbol": (
                            ref.symbol
                        ),
                    }
                    for ref in (
                        cross_analysis.imports
                    )
                ],
                "function_calls": [
                    {
                        "source": (
                            ref.source_file
                        ),
                        "target": (
                            ref.target_file
                        ),
                        "symbol": (
                            ref.symbol
                        ),
                    }
                    for ref in (
                        cross_analysis.function_calls
                    )
                ],
            }

            architecture_context = {
                "cyclic_dependencies": (
                    architecture_report.cycles
                ),
                "highly_connected_files": (
                    health_report
                    .highly_connected_files
                ),
                "health_score": (
                    health_report
                    .health_score
                ),
            }

            risk_context = {
                "risks": [
                    {
                        "type": (
                            risk.risk_type
                        ),
                        "severity": (
                            risk.severity
                        ),
                        "file": (
                            risk.file
                        ),
                        "description": (
                            risk.description
                        ),
                    }
                    for risk in (
                        risk_report.risks
                    )
                ]
            }

            code_quality_context = (
                quality_report.model_dump()
            )

        elif task.repo_path:

            # Task `repo`: analisi aggregata sull'intero repository.
            # Diversamente dai task con file_path, qui non c'e' un
            # singolo file da analizzare. Tutto il context e' aggregato
            # a livello di progetto.

            project_files = (
                ProjectScanner()
                .scan(task.repo_path)
            )

            graph = (
                ProjectGraphBuilder()
                .build(task.repo_path)
            )

            architecture_report = (
                ArchitectureAnalyzer()
                .detect_cycles(
                    graph
                )
            )

            health_report = (
                RepositoryHealthAnalyzer()
                .analyze(
                    graph=graph,
                    cycles=(
                        architecture_report.cycles
                    ),
                )
            )

            risk_report = (
                ArchitecturalRiskAnalyzer()
                .analyze(graph)
            )

            cross_analysis = (
                CrossFileAnalyzer()
                .analyze(project_files)
            )

            # repository_context: aggregato di alto livello sul
            # progetto intero (non focalizzato su un singolo file).
            repository_context = {
                "project_size": (
                    health_report.total_files
                ),
                "total_dependencies": (
                    health_report.total_dependencies
                ),
                "repo_path": task.repo_path,
            }

            architecture_context = {
                "cyclic_dependencies": (
                    architecture_report.cycles
                ),
                "highly_connected_files": (
                    health_report
                    .highly_connected_files
                ),
                "health_score": (
                    health_report
                    .health_score
                ),
            }

            risk_context = {
                "risks": [
                    {
                        "type": (
                            risk.risk_type
                        ),
                        "severity": (
                            risk.severity
                        ),
                        "file": (
                            risk.file
                        ),
                        "description": (
                            risk.description
                        ),
                    }
                    for risk in (
                        risk_report.risks
                    )
                ]
            }

            cross_file_context = {
                "imports": [
                    {
                        "source": (
                            ref.source_file
                        ),
                        "target": (
                            ref.target_file
                        ),
                        "symbol": (
                            ref.symbol
                        ),
                    }
                    for ref in (
                        cross_analysis.imports
                    )
                ],
                "function_calls": [
                    {
                        "source": (
                            ref.source_file
                        ),
                        "target": (
                            ref.target_file
                        ),
                        "symbol": (
                            ref.symbol
                        ),
                    }
                    for ref in (
                        cross_analysis.function_calls
                    )
                ],
            }

            # code_quality aggregato sull'intero progetto.
            # Si itera su ogni file del progetto e si accumulano
            # i risultati nel report aggregato.
            aggregated_god_classes: list[str] = []
            aggregated_long_methods: list[str] = []
            aggregated_complexity_warnings: list[str] = []
            aggregated_dead_functions: list[str] = []
            aggregated_architectural_risks: list[str] = []

            for project_file in project_files:

                try:
                    file_raw = (
                        FileReader.read(
                            project_file.path
                        )
                    )

                    file_tree = ast.parse(
                        file_raw
                    )

                    file_semantic = (
                        SemanticAnalyzer()
                        .analyze_file(
                            project_file.path
                        )
                    )

                    file_quality = (
                        CodeQualityAnalyzer()
                        .analyze(
                            semantic=file_semantic,
                            graph=graph,
                            tree=file_tree,
                        )
                    )

                    aggregated_god_classes.extend(
                        file_quality.god_classes
                    )

                    aggregated_long_methods.extend(
                        file_quality.long_methods
                    )

                    aggregated_complexity_warnings.extend(
                        file_quality.complexity_warnings
                    )

                    aggregated_dead_functions.extend(
                        file_quality.dead_functions
                    )

                    aggregated_architectural_risks.extend(
                        file_quality.architectural_risks
                    )

                except (
                    FileNotFoundError,
                    UnicodeDecodeError,
                    SyntaxError,
                ):
                    # File non leggibile o non parsabile:
                    # skip senza interrompere la scansione.
                    continue

            code_quality_context = {
                "god_classes": (
                    aggregated_god_classes
                ),
                "long_methods": (
                    aggregated_long_methods
                ),
                "complexity_warnings": (
                    aggregated_complexity_warnings
                ),
                "dead_functions": (
                    aggregated_dead_functions
                ),
                "architectural_risks": (
                    aggregated_architectural_risks
                ),
            }

            # semantic_context resta vuoto: non c'e' un file
            # singolo da analizzare. L'overview deriva dagli
            # aggregati sopra.
            semantic_context = {
                "functions": [],
                "classes": [],
                "imports": [],
                "calls": [],
            }

        task_with_context = (
            task.model_copy(
                update={
                    "raw_input": (
                        file_content
                    ),
                    "options": {
                        **task.options,
                        "metadata": (
                            metadata_dump
                        ),
                        "repository_context": (
                            repository_context
                        ),
                        "architecture_context": (
                            architecture_context
                        ),
                        "semantic_context": (
                            semantic_context
                        ),
                        "cross_file_context": (
                            cross_file_context
                        ),
                        "risk_context": (
                            risk_context
                        ),
                        "code_quality_context": (
                            code_quality_context
                        ),
                        "impacted_files_content": (
                            impacted_files_content
                        ),
                        "range_spec": task.git_range or "",
                    },
                }
            )
        )

        agent = self._build_agent(
            agent_name
        )

        output = agent.run(
            task=task_with_context,
            skills=loaded_skills,
        )

        verification = (
            self.verifier.check(
                output
            )
        )

        return self.assembler.build(
            output,
            verification,
        )