from pathlib import Path

from aiops_agent.config import Settings


def test_settings_defaults_use_project_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env()

    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / "data"
    assert settings.logs_dir == tmp_path / "data" / "logs"
    assert settings.reports_dir == tmp_path / "reports"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_api_key is None
