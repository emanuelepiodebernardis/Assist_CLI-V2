"""Il SkillResolver deve trovare le skill anche fuori dalla repo root."""


from assist.core.skill_resolver import SkillResolver


def test_fallback_alla_root_del_package(tmp_path, monkeypatch):
    # cwd in una directory qualunque, senza assist/skills
    monkeypatch.chdir(tmp_path)

    resolver = SkillResolver()

    assert resolver.skills_path.exists()
    assert (resolver.skills_path / "project_rules").exists()


def test_path_esplicito_non_toccato(tmp_path):
    custom = tmp_path / "mie_skills"
    custom.mkdir()

    resolver = SkillResolver(skills_path=str(custom))

    assert resolver.skills_path == custom
