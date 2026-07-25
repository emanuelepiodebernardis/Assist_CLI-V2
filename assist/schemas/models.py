from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    severity: Literal[
        "critical",
        "high",
        "medium",
        "low",
    ]
    message: str
    location: str | None = None


class SkillInputs(BaseModel):
    """Dati del context che la skill richiede (v3.0).

    Lista i campi del PromptContext o della task input che la skill legge
    nel suo prompt finale. Validata al caricamento: se un campo richiesto
    non esiste nel sistema, errore esplicito.
    """

    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class SkillOutputSections(BaseModel):
    """Sezioni dell'output prodotto dalla skill (solo per format=markdown) (v3.0).

    Le sezioni `required` devono apparire nell'output; le `optional`
    possono apparire o no. Usate dal verifier per il check `format:
    section_headers`.
    """

    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class SkillOutputs(BaseModel):
    """Struttura dell'output prodotto dalla skill (v3.0).

    `format` deve essere coerente con `task_type` della skill:
    - task_type prose -> format markdown
    - task_type code -> format python (o altri linguaggi futuri)
    - task_type json -> format json

    `sections` e' valorizzato solo per format=markdown.
    """

    format: Literal["markdown", "python", "json"]
    sections: SkillOutputSections | None = None


class SkillProcess(BaseModel):
    """Parametri del loop di esecuzione dell'agent (v3.0).

    - max_corrections: numero massimo di iterazioni
      generate_draft -> self_check -> correct. Default 1.
    - quality_threshold: soglia sotto la quale is_valid=false. Default 0.70.
      Coerente con la rubrica deterministica della sezione 9 delle skill.
    """

    max_corrections: int = Field(default=1, ge=0, le=3)
    quality_threshold: float = Field(default=0.70, ge=0.0, le=1.0)


class SkillVerifier(BaseModel):
    """Configurazione del GlobalVerifier per la skill (v3.0).

    Modi disponibili:
    - syntax: noop (no check) | ast (parse Python AST)
    - format: noop | section_headers (verifica sezioni di outputs.sections)
    - coherence: noop | rubric (delega alla rubrica della sezione 9 del body)

    Combinazioni tipiche:
    - task_type prose: syntax=noop, format=section_headers, coherence=rubric
    - task_type code: syntax=ast, format=noop, coherence=rubric
    - task_type json: syntax=noop, format=noop, coherence=rubric
    """

    syntax: Literal["noop", "ast"] = "noop"
    format: Literal["noop", "section_headers"] = "noop"
    coherence: Literal["noop", "rubric"] = "noop"


class Skill(BaseModel):
    """Skill di Assist CLI.

    Campi v2.5 (originali, sempre presenti):
    - name: identificatore univoco snake_case
    - content: contenuto raw del file SKILL.md (frontmatter + body markdown)

    Campi v3.0 (opzionali, popolati solo se la skill dichiara version: 3.0):
    - version: "2.5" o "3.0". Default "2.5" per retrocompatibilita'.
    - task_type, inputs, outputs, process, verifier: parsati dal frontmatter
      dal SkillResolver solo se la skill e' v3.0. Per skill v2.5, restano None.

    Comportamento del codice esistente:
    - Il codice che usa skill.content (raw text) continua a funzionare invariato
      per qualunque versione della skill.
    - Il codice nuovo (Agent generico, PromptBuilder dichiarativo, verifier
      configurabile) usa i campi v3.0 quando presenti.
    """

    name: str
    content: str

    # Campi v3.0 (opzionali, default a valori v2.5-compatibili)
    version: str = "2.5"
    task_type: Literal["prose", "code", "json"] | None = None
    inputs: SkillInputs | None = None
    outputs: SkillOutputs | None = None
    process: SkillProcess | None = None
    verifier: SkillVerifier | None = None


class TaskInput(BaseModel):
    command: str
    file_path: str | None = None
    language: str = "python"
    raw_input: str | None = None
    options: dict = Field(default_factory=dict)
    git_range: str | None = None
    repo_path: str | None = None


class ValidationReport(BaseModel):
    is_valid: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    clarity_score: float = Field(ge=0.0, le=1.0)
    issues: list[Issue] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    content: str
    agent_name: str
    task_type: str
    quality_score: float = Field(ge=0.0, le=1.0)
    iterations_used: int = Field(ge=1)


class VerificationResult(BaseModel):
    passed: bool
    syntax_ok: bool
    coherent_with_task: bool
    format_ok: bool
    warnings: list[str] = Field(default_factory=list)
    fatal_issues: list[str] = Field(default_factory=list)


class RegistryResult(BaseModel):
    agent: str
    skills: list[str]


class FileMetadata(BaseModel):
    path: str
    size_bytes: int
    lines: int


class ProjectFileNode(BaseModel):
    path: str
    module: str
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    size_bytes: int
    lines: int


class ProjectGraph(BaseModel):
    root: str
    files: list[ProjectFileNode] = Field(default_factory=list)


class ProjectContextFile(BaseModel):
    path: str
    module: str
    importance_score: float = Field(ge=0.0, le=1.0)
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)


class ProjectContext(BaseModel):
    root: str
    summary: str
    total_files: int
    entry_points: list[str] = Field(default_factory=list)
    primary_files: list[ProjectContextFile] = Field(default_factory=list)


class ArchitectureReport(BaseModel):
    has_cycles: bool
    cycles: list[list[str]] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)


class RepositoryHealthReport(BaseModel):
    total_files: int
    total_dependencies: int
    cyclic_dependencies: int
    highly_connected_files: list[str] = Field(default_factory=list)
    health_score: float = Field(ge=0.0, le=1.0)
    issues: list[Issue] = Field(default_factory=list)


class FunctionInfo(BaseModel):
    name: str
    line_count: int = 0
    complexity: int = 1
    lineno: int = 0
    end_lineno: int | None = None
    decorators: list[str] = Field(default_factory=list)


class ClassInfo(BaseModel):
    name: str
    lineno: int = 0
    end_lineno: int | None = None
    methods: list[FunctionInfo] = Field(default_factory=list)


class SemanticAnalysis(BaseModel):
    path: str = ""
    functions: list[FunctionInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    calls: list[str] = Field(default_factory=list)


class CrossFileReference(BaseModel):
    source_file: str
    target_file: str
    symbol: str


class CrossFileAnalysis(BaseModel):
    imports: list[CrossFileReference] = Field(default_factory=list)
    function_calls: list[CrossFileReference] = Field(default_factory=list)


class ArchitecturalRisk(BaseModel):
    risk_type: str
    severity: str
    file: str
    description: str


class ArchitecturalRiskReport(BaseModel):
    risks: list[ArchitecturalRisk] = Field(default_factory=list)


class GodClassFinding(BaseModel):
    class_name: str
    method_count: int
    severity: str
    recommendation: str


class GodClassReport(BaseModel):
    findings: list[GodClassFinding] = Field(default_factory=list)


class LongMethodFinding(BaseModel):
    function_name: str
    line_count: int
    severity: str
    recommendation: str


class LongMethodReport(BaseModel):
    findings: list[LongMethodFinding] = Field(default_factory=list)


class CodeQualityReport(BaseModel):
    complexity_warnings: list[str] = Field(default_factory=list)
    dead_functions: list[str] = Field(default_factory=list)
    architectural_risks: list[str] = Field(default_factory=list)
    long_methods: list[str] = Field(default_factory=list)
    god_classes: list[str] = Field(default_factory=list)


FunctionSymbol = FunctionInfo
ClassSymbol = ClassInfo
SemanticFileAnalysis = SemanticAnalysis

class PromptContext(BaseModel):
    file_path: str = ""
    file_metadata: dict = Field(default_factory=dict)
    repository_context: dict = Field(default_factory=dict)
    architecture_context: dict = Field(default_factory=dict)
    semantic_context: dict = Field(default_factory=dict)
    cross_file_context: dict = Field(default_factory=dict)
    risk_context: dict = Field(default_factory=dict)
    code_quality_context: dict = Field(default_factory=dict)

class FinalOutput(BaseModel):
    raw_content: str
    verification: VerificationResult
    agent_name: str
    task_type: str
    quality_score: float = Field(ge=0.0, le=1.0)
    iterations_used: int = Field(ge=1, default=1)

class FileDiff(BaseModel):
    """Diff di un singolo file modificato dal range git.

    Rappresenta cosa e' cambiato in un file specifico:
    quante righe aggiunte/rimosse e l'output testuale del diff
    per quel file (sezione "hunks").
    """

    path: str

    additions: int = 0

    deletions: int = 0

    hunks: str = ""


class GitDiff(BaseModel):
    """Risultato dell'estrazione di un diff git su un range.

    Aggrega tutti i FileDiff prodotti dal range specificato,
    piu' metadati aggregati (summary) e l'output raw di git diff
    (utile per il prompt completo da inviare all'LLM).
    """

    range_spec: str

    files: list[FileDiff] = []

    files_changed: int = 0

    total_additions: int = 0

    total_deletions: int = 0

    raw_diff: str = ""
