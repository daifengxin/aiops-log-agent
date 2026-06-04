from aiops_agent.config import Settings


def test_settings_defaults_use_project_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env()

    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / "data"
    assert settings.logs_dir == tmp_path / "data" / "logs"
    assert settings.reports_dir == tmp_path / "reports"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_api_key is None


def test_settings_loads_env_from_explicit_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    cwd = tmp_path / "cwd"
    project_root.mkdir()
    cwd.mkdir()
    (project_root / ".env").write_text(
        "GEMINI_API_KEY=project-key\nGEMINI_MODEL=gemini-test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(cwd)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = Settings.from_env(project_root=project_root)

    assert settings.project_root == project_root
    assert settings.gemini_api_key == "project-key"
    assert settings.gemini_model == "gemini-test"


def test_ensure_dirs_creates_runtime_directories(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)

    settings.ensure_dirs()

    assert settings.logs_dir.is_dir()
    assert settings.rag_dir.is_dir()
    assert settings.eval_dir.is_dir()
    assert settings.figures_dir.is_dir()
