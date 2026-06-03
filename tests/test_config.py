from pathlib import Path
from smart_renamer.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.template == "{tags}_{index}"
    assert cfg.dry_run is True


def test_loads_from_file(tmp_path):
    config_file = tmp_path / "smart_renamer.toml"
    config_file.write_text("""
[general]
template = "{date}_{tags}"
dry_run = false

[gemini]
enabled = true
api_key = "test-key"
""")
    cfg = Config(config_file)
    assert cfg.template == "{date}_{tags}"
    assert cfg.dry_run is False
    assert cfg.gemini_enabled is True
    assert cfg.gemini_api_key == "test-key"
