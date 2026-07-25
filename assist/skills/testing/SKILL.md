---
name: testing
version: 2.0
applies_to: [generate, review]
load_examples: true
load_templates: false
priority: high
max_output_words:
  concise: unlimited
  verbose: unlimited
conflict_resolution: >
  In caso di conflitto con project_rules, project_rules ha precedenza.
  Regola specifica: i test non seguono il limite di 40 righe per funzione
  quando un singolo test case richiede setup esteso. Ogni test resta
  comunque focalizzato su un solo comportamento.
description: >
  Regole per la scrittura di test Python con pytest. Include principio
  di determinismo assoluto, naming comportamentale, struttura AAA,
  quattro categorie obbligatorie, MockLLMClient canonico, fixture
  condivise, e calibrazione degli invarianti di sistema.
---

════════════════════════════════════════════════════════════
TESTING — REGOLE OPERATIVE
════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════
SEZIONE 1 — PRINCIPIO FONDAMENTALE: DETERMINISMO ASSOLUTO
════════════════════════════════════════════════════════════

Un test che a volte passa e a volte fallisce non esiste.
È rumore che maschera bug reali.

Ogni test deve essere:
  - Deterministico: stesso risultato ogni esecuzione
  - Offline: zero chiamate di rete (incluse chiamate al modello LLM)
  - Indipendente dall'ordine: non dipende da altri test
  - Indipendente dal tempo: non usa datetime.now() senza mock
  - Indipendente dal filesystem reale: usa tmp_path, non path assoluti

Il MockLLMClient non è opzionale. È la prima cosa da costruire.
Senza di esso nessun test degli agenti è deterministico.

════════════════════════════════════════════════════════════
SEZIONE 2 — COMPORTAMENTO VS IMPLEMENTAZIONE
════════════════════════════════════════════════════════════

Un test verifica il COMPORTAMENTO OSSERVABILE, non l'implementazione.

  SBAGLIATO — testa l'implementazione (fragile):
    def test_agent_calls_llm_three_times():
        mock_llm = Mock()
        agent.run(task)
        assert mock_llm.complete.call_count == 3
        # Si rompe ad ogni refactoring, anche se il comportamento è corretto

  CORRETTO — testa il comportamento (stabile):
    def test_agent_returns_valid_output_for_generate_task():
        agent = GeneratorAgent(llm=MockLLMClient(response=VALID_PYTHON))
        result = agent.run(generate_task, skills=[])
        assert isinstance(result, AgentOutput)
        assert result.quality_score >= 0.0
        assert len(result.content) > 0
        # Passa indipendentemente da quante volte chiama il modello

════════════════════════════════════════════════════════════
SEZIONE 3 — NAMING: DESCRIVI IL COMPORTAMENTO
════════════════════════════════════════════════════════════

Il nome del test è la documentazione del comportamento atteso.
Deve essere leggibile senza guardare il corpo del test.

Pattern: test_<soggetto>_<condizione>_<risultato_atteso>

  SBAGLIATO:
    def test_load_skill():
    def test_registry():
    def test_agent_run():

  CORRETTO:
    def test_load_skill_raises_file_not_found_when_path_missing():
    def test_registry_maps_review_command_to_reviewer_agent():
    def test_agent_stops_self_check_loop_at_max_corrections():
    def test_global_verifier_rejects_output_with_invalid_syntax():
    def test_quality_score_is_always_between_zero_and_one():

════════════════════════════════════════════════════════════
SEZIONE 4 — STRUTTURA AAA: OBBLIGATORIA
════════════════════════════════════════════════════════════

Ogni test segue Arrange → Act → Assert con commenti espliciti
quando il test è più lungo di 5 righe.

  def test_registry_maps_review_command_to_reviewer_agent():
      # Arrange
      registry = Registry.from_yaml(FIXTURE_REGISTRY_PATH)

      # Act
      agent_class, skill_names = registry.resolve("review")

      # Assert
      assert agent_class is ReviewerAgent
      assert "code_review" in skill_names
      assert "project_rules" in skill_names

Ogni test ha UNA sola asserzione logica.
Più assert sullo stesso oggetto sono accettabili.
Assert su oggetti diversi in un solo test non è accettabile.

════════════════════════════════════════════════════════════
SEZIONE 5 — QUATTRO CATEGORIE OBBLIGATORIE
════════════════════════════════════════════════════════════

Per ogni componente, scrivi test in queste quattro categorie.
Se manca una categoria, il componente non è testato correttamente.

── 1. HAPPY PATH ─────────────────────────────────────────

  Comportamento corretto su input valido e tipico.

    def test_skill_resolver_loads_valid_skill_by_name():
        resolver = SkillResolver(skills_root=FIXTURE_SKILLS_PATH)
        skill = resolver.load_one("project_rules")
        assert skill.name == "project_rules"
        assert skill.content  # non vuoto

── 2. EDGE CASE ──────────────────────────────────────────

  Casi limite prevedibili: vuoto, zero, None, lista vuota,
  stringa vuota, valore massimo, valore minimo.

    def test_agent_self_check_loop_stops_at_max_corrections():
        llm = MockLLMClient(response=LOW_QUALITY_OUTPUT)
        agent = ConcreteAgent(llm=llm, max_corrections=2)
        result = agent.run(task, skills=[])
        assert result.iterations_used <= 2  # mai supera il limite

    def test_assembler_handles_empty_agent_output_without_crashing():
        assembler = ResponseAssembler()
        result = assembler.build(AgentOutput(content="", ...))
        assert result is not None  # non crasha, gestisce il caso

── 3. ERROR PATH ─────────────────────────────────────────

  Eccezioni attese su input non valido.

    def test_load_skill_raises_file_not_found_on_missing_path():
        resolver = SkillResolver(skills_root=Path("/tmp/nonexistent"))
        with pytest.raises(FileNotFoundError, match="project_rules"):
            resolver.load_one("project_rules")

    def test_registry_raises_unknown_command_error_on_invalid_command():
        registry = Registry.from_yaml(FIXTURE_REGISTRY_PATH)
        with pytest.raises(UnknownCommandError, match="'unknown'"):
            registry.resolve("unknown")

    def test_global_verifier_rejects_output_with_syntax_error():
        verifier = GlobalVerifier()
        result = verifier.check("def broken(:\n    pass", task)
        assert not result.syntax_ok
        assert not result.passed

── 4. INVARIANTI DI SISTEMA ──────────────────────────────

  Proprietà sempre vere, indipendentemente dall'input.
  Usa @pytest.mark.parametrize per coprire tutti i casi.

    @pytest.mark.parametrize("command", ["generate", "review", "refactor", "explain"])
    def test_all_commands_are_mapped_in_registry(command: str):
        registry = Registry.from_yaml(FIXTURE_REGISTRY_PATH)
        agent_class, skill_names = registry.resolve(command)
        assert agent_class is not None
        assert len(skill_names) >= 1

    @pytest.mark.parametrize("skill_name", [
        "project_rules", "python_generation", "code_review",
        "refactor", "documentation", "testing",
    ])
    def test_all_mvp_skills_are_loadable(skill_name: str):
        resolver = SkillResolver(skills_root=REAL_SKILLS_PATH)
        skill = resolver.load_one(skill_name)
        assert skill.name == skill_name
        assert skill.content.strip()

    def test_agent_output_quality_score_is_always_in_valid_range():
        llm = MockLLMClient(response=VALID_PYTHON)
        agent = GeneratorAgent(llm=llm)
        result = agent.run(sample_task, skills=[])
        assert 0.0 <= result.quality_score <= 1.0

    def test_self_check_loop_never_exceeds_max_corrections():
        # Test con mock che non converge mai
        llm = MockLLMClient(response=LOW_QUALITY_OUTPUT)
        for max_c in [1, 2, 3]:
            agent = ConcreteAgent(llm=llm, max_corrections=max_c)
            result = agent.run(sample_task, skills=[])
            assert result.iterations_used <= max_c

════════════════════════════════════════════════════════════
SEZIONE 6 — MOCK E FIXTURE: STANDARD CANONICO
════════════════════════════════════════════════════════════

── MOCKCLIENT CANONICO ───────────────────────────────────

  Implementa sempre questo pattern. Non usare unittest.Mock
  per il client LLM: è troppo permissivo e nasconde errori
  di interfaccia.

  class MockLLMClient:
      """Client LLM deterministico per i test.

      Restituisce sempre la stessa risposta preconfigurata.
      Non fa mai chiamate di rete.

      Attributes:
          _response: Risposta fissa da restituire.
          call_count: Numero di chiamate (per asserzioni di integrazione).
          prompts_received: Lista dei prompt ricevuti (per asserzioni).
      """

      def __init__(self, response: str) -> None:
          self._response = response
          self.call_count: int = 0
          self.prompts_received: list[str] = []

      def complete(self, prompt: str, system: str = "") -> str:
          self.call_count += 1
          self.prompts_received.append(prompt)
          return self._response

── FIXTURE IN CONFTEST.PY ────────────────────────────────

  FIXTURES_PATH = Path(__file__).parent / "fixtures"
  SKILLS_PATH = Path(__file__).parent.parent / "assist" / "skills"

  @pytest.fixture(scope="session")
  def valid_python_output() -> str:
      """Codice Python sintatticamente corretto e ben strutturato."""
      return (FIXTURES_PATH / "valid_python_output.txt").read_text(encoding="utf-8")

  @pytest.fixture(scope="session")
  def low_quality_output() -> str:
      """Codice funzionante ma con magic number, nessun type hint, except generico."""
      return (FIXTURES_PATH / "low_quality_output.txt").read_text(encoding="utf-8")

  @pytest.fixture
  def mock_llm_valid(valid_python_output: str) -> MockLLMClient:
      return MockLLMClient(response=valid_python_output)

  @pytest.fixture
  def mock_llm_low_quality(low_quality_output: str) -> MockLLMClient:
      return MockLLMClient(response=low_quality_output)

  @pytest.fixture
  def sample_generate_task(tmp_path: Path) -> TaskInput:
      spec = tmp_path / "spec.txt"
      spec.write_text("Genera una funzione che somma due interi.")
      return TaskInput(command="generate", file_path=spec, language="python")

  @pytest.fixture
  def sample_review_task(tmp_path: Path) -> TaskInput:
      source = tmp_path / "sample.py"
      source.write_text(
          (FIXTURES_PATH / "samples" / "dirty_code.py").read_text(encoding="utf-8"),
          encoding="utf-8",
      )
      return TaskInput(command="review", file_path=source, language="python")

── FIXTURE VS VARIABILE DI MODULO ───────────────────────

  Usa @pytest.fixture per oggetti con stato o che richiedono
  setup/teardown (file temporanei con tmp_path).

  Usa variabili di modulo per stringhe statiche, path, costanti.

════════════════════════════════════════════════════════════
SEZIONE 7 — STRUTTURA DIRECTORY DEI TEST
════════════════════════════════════════════════════════════

  tests/
  ├── conftest.py                     # MockLLMClient + fixture condivise
  ├── fixtures/
  │   ├── valid_python_output.txt     # output LLM: codice Python valido
  │   ├── low_quality_output.txt      # funzionante ma con problemi noti
  │   ├── invalid_python_output.txt   # errori di sintassi
  │   ├── registry.yaml               # registry minimale per test
  │   └── samples/
  │       ├── clean_code.py           # codice ben scritto
  │       └── dirty_code.py           # codice con problemi noti e catalogati
  ├── unit/
  │   ├── test_schemas.py             # validazione Pydantic
  │   ├── test_registry.py            # routing task→agente→skills
  │   ├── test_skill_resolver.py      # caricamento skills
  │   ├── test_self_validation_loop.py
  │   ├── test_global_verifier.py     # ast.parse + placeholder check
  │   └── test_assembler.py
  └── integration/
      ├── test_cli_commands.py        # CLI con typer.testing.CliRunner
      └── test_agent_with_skills.py   # agenti + skills reali + MockLLM

════════════════════════════════════════════════════════════
SEZIONE 8 — TEST CLI CON TYPER
════════════════════════════════════════════════════════════

  from typer.testing import CliRunner
  from assist.cli.main import app

  runner = CliRunner()

  def test_review_command_exits_zero_on_valid_file(tmp_python_file: Path):
      result = runner.invoke(app, ["review", str(tmp_python_file)])
      assert result.exit_code == 0
      assert "## Sommario" in result.output   # verifica formato

  def test_review_command_exits_nonzero_on_missing_file():
      result = runner.invoke(app, ["review", "/tmp/nonexistent_12345.py"])
      assert result.exit_code != 0
      assert "non trovato" in result.output.lower()

  def test_help_command_shows_all_four_subcommands():
      result = runner.invoke(app, ["--help"])
      assert result.exit_code == 0
      for cmd in ["generate", "review", "refactor", "explain"]:
          assert cmd in result.output

════════════════════════════════════════════════════════════
SEZIONE 9 — CHECKLIST SELF-VERIFICA PRIMA DI RESTITUIRE
════════════════════════════════════════════════════════════

  [ ] Ogni test ha un nome che descrive il comportamento atteso?
  [ ] Ogni test segue la struttura AAA?
  [ ] Happy path, edge case, error path e invarianti sono coperti?
  [ ] Nessun test fa chiamate reali al modello LLM?
  [ ] MockLLMClient è usato invece di unittest.Mock per il client?
  [ ] Le fixture sono in conftest.py e riutilizzabili?
  [ ] I test sono deterministici? (no datetime.now(), no random, no rete)
  [ ] I test sono indipendenti dall'ordine di esecuzione?
  [ ] Le asserzioni hanno match= nei pytest.raises per verificare il messaggio?
  [ ] Nessun test testa l'implementazione invece del comportamento?
