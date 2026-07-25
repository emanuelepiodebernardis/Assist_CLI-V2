# Esempio: conftest.py e test suite per il SkillResolver
# Questo file mostra lo standard atteso per i test di Assist CLI.
# Struttura, naming, fixture e asserzioni sono tutti canonici.

# ─────────────────────────────────────────────────────────────
# conftest.py
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

from pathlib import Path

import pytest

# Percorsi fissi
FIXTURES_PATH = Path(__file__).parent / "fixtures"
SKILLS_PATH = Path(__file__).parent.parent / "assist" / "skills"


class MockLLMClient:
    """Client LLM deterministico per i test.

    Restituisce sempre la stessa risposta preconfigurata.
    Non fa mai chiamate di rete.

    Attributes:
        _response: Risposta fissa da restituire.
        call_count: Numero di chiamate ricevute (per asserzioni).
    """

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0

    def complete(self, prompt: str, system: str = "") -> str:
        self.call_count += 1
        return self._response


@pytest.fixture(scope="session")
def valid_python_response() -> str:
    """Output LLM valido: codice Python sintatticamente corretto."""
    return (FIXTURES_PATH / "valid_python_output.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def invalid_python_response() -> str:
    """Output LLM invalido: codice con errori di sintassi."""
    return (FIXTURES_PATH / "invalid_python_output.txt").read_text(encoding="utf-8")


@pytest.fixture
def mock_llm_valid(valid_python_response: str) -> MockLLMClient:
    """LLM mock che restituisce codice Python valido."""
    return MockLLMClient(response=valid_python_response)


@pytest.fixture
def mock_llm_invalid(invalid_python_response: str) -> MockLLMClient:
    """LLM mock che restituisce output con sintassi invalida."""
    return MockLLMClient(response=invalid_python_response)


@pytest.fixture
def tmp_python_file(tmp_path: Path) -> Path:
    """File Python temporaneo con codice semplice e valido."""
    f = tmp_path / "sample.py"
    f.write_text(
        (FIXTURES_PATH / "samples" / "dirty_code.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return f


# ─────────────────────────────────────────────────────────────
# tests/unit/test_skill_resolver.py
# ─────────────────────────────────────────────────────────────

from pathlib import Path

import pytest

# Queste import sono simboliche: si risolvono nel progetto reale
# from assist.core.skill_resolver import SkillResolver
# from assist.schemas.models import Skill


class TestSkillResolverHappyPath:
    """Test del comportamento corretto su input valido."""

    def test_loads_single_skill_by_name(self, tmp_skills_root):
        resolver = SkillResolver(skills_root=tmp_skills_root)
        skill = resolver.load_one("project_rules")

        assert skill.name == "project_rules"
        assert len(skill.content) > 0

    def test_loads_multiple_skills_in_order(self, tmp_skills_root):
        resolver = SkillResolver(skills_root=tmp_skills_root)
        skills = resolver.load(["project_rules", "python_generation"])

        assert len(skills) == 2
        assert skills[0].name == "project_rules"
        assert skills[1].name == "python_generation"

    def test_loaded_skill_has_required_metadata(self, tmp_skills_root):
        resolver = SkillResolver(skills_root=tmp_skills_root)
        skill = resolver.load_one("project_rules")

        assert skill.name
        assert skill.version
        assert skill.applies_to
        assert isinstance(skill.applies_to, list)


class TestSkillResolverEdgeCases:
    """Test dei casi limite."""

    def test_raises_on_empty_skill_list(self, tmp_skills_root):
        resolver = SkillResolver(skills_root=tmp_skills_root)

        with pytest.raises(ValueError, match="almeno una skill"):
            resolver.load([])

    def test_raises_on_nonexistent_skill(self, tmp_skills_root):
        resolver = SkillResolver(skills_root=tmp_skills_root)

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            resolver.load_one("nonexistent")

    def test_raises_on_nonexistent_skills_root(self):
        resolver = SkillResolver(skills_root=Path("/tmp/does_not_exist_12345"))

        with pytest.raises(FileNotFoundError):
            resolver.load_one("project_rules")

    def test_raises_on_malformed_frontmatter(self, tmp_path):
        broken_skill = tmp_path / "broken" / "SKILL.md"
        broken_skill.parent.mkdir()
        broken_skill.write_text("no frontmatter here\njust text", encoding="utf-8")

        resolver = SkillResolver(skills_root=tmp_path)

        with pytest.raises(ValueError, match="frontmatter"):
            resolver.load_one("broken")


class TestSkillResolverInvariants:
    """Invarianti: proprietà vere per ogni skill valida."""

    @pytest.mark.parametrize("skill_name", [
        "project_rules",
        "python_generation",
        "code_review",
        "refactor",
        "documentation",
        "testing",
    ])
    def test_all_mvp_skills_are_loadable(self, skill_name):
        """Tutte le skill dell'MVP esistono e sono caricabili."""
        resolver = SkillResolver(skills_root=SKILLS_PATH)
        skill = resolver.load_one(skill_name)

        assert skill.name == skill_name
        assert skill.content.strip()  # non vuota

    @pytest.mark.parametrize("skill_name", [
        "project_rules",
        "python_generation",
        "code_review",
        "refactor",
        "documentation",
        "testing",
    ])
    def test_all_skills_have_applies_to_as_list(self, skill_name):
        """applies_to è sempre una lista, mai None o stringa."""
        resolver = SkillResolver(skills_root=SKILLS_PATH)
        skill = resolver.load_one(skill_name)

        assert isinstance(skill.applies_to, list)
        assert len(skill.applies_to) >= 1


# ─────────────────────────────────────────────────────────────
# tests/unit/test_self_validation_loop.py
# ─────────────────────────────────────────────────────────────

class TestSelfValidationLoop:
    """Test del loop di auto-verifica nel BaseAgent."""

    def test_loop_stops_at_max_corrections(self, mock_llm_low_quality):
        """Il loop non supera mai max_corrections, anche se la qualità è bassa."""
        agent = ConcreteTestAgent(llm=mock_llm_low_quality, max_corrections=2)
        result = agent.run(sample_task, skills=[])

        assert result.iterations_used <= 2

    def test_loop_stops_early_on_valid_output(self, mock_llm_valid):
        """Il loop si ferma prima di max_corrections se la qualità è sufficiente."""
        agent = ConcreteTestAgent(llm=mock_llm_valid, max_corrections=2)
        result = agent.run(sample_task, skills=[])

        # Se il primo draft è valido, si ferma a 1 iterazione
        assert result.iterations_used == 1

    def test_output_quality_score_is_always_in_range(self, mock_llm_valid):
        """quality_score è sempre nel range [0.0, 1.0]."""
        agent = ConcreteTestAgent(llm=mock_llm_valid)
        result = agent.run(sample_task, skills=[])

        assert 0.0 <= result.quality_score <= 1.0

    def test_returns_best_draft_when_not_converging(self, mock_llm_low_quality):
        """Restituisce il draft con score più alto, non l'ultimo prodotto."""
        agent = ConcreteTestAgent(
            llm=mock_llm_low_quality,
            max_corrections=2,
            quality_threshold=0.99,  # soglia impossibile da raggiungere
        )
        result = agent.run(sample_task, skills=[])

        # Deve comunque restituire qualcosa, non fallire silenziosamente
        assert result.content
        assert result.iterations_used == 2
