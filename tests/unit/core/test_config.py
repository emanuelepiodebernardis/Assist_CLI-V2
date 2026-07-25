from assist.core.config import ConfigLoader


def test_config_loader_reads_settings():
    settings = ConfigLoader().load()

    assert settings.temperature == 0.2
    assert settings.quality.max_self_corrections == 2