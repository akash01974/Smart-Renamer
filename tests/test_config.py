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


def test_merges_user_config_with_project_config(tmp_path, monkeypatch):
    project_cfg = tmp_path / "smart_renamer.toml"
    project_cfg.write_text("""
[general]
template = "{tags}_{index}"
dry_run = true

[gemini]
enabled = true
api_key = ""
""")
    user_cfg_dir = tmp_path / ".config" / "smart_renamer"
    user_cfg_dir.mkdir(parents=True)
    user_cfg = user_cfg_dir / "config.toml"
    user_cfg.write_text("""
[gemini]
enabled = true
api_key = "user-key-from-config"
""")
    monkeypatch.setattr("smart_renamer.config.Path.cwd", lambda: tmp_path)
    monkeypatch.setattr("smart_renamer.config.Path.home", lambda: tmp_path)
    cfg = Config()
    assert cfg.gemini_enabled is True
    assert cfg.gemini_api_key == "user-key-from-config"
