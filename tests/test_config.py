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


def test_settings_environment_variables_override_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "GEMINI_API_KEY=file-key\nGEMINI_MODEL=gemini-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env")

    settings = Settings.from_env(project_root=tmp_path)

    assert settings.gemini_api_key == "env-key"
    assert settings.gemini_model == "gemini-env"


def test_settings_env_values_do_not_leak_between_project_roots(tmp_path, monkeypatch):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / ".env").write_text(
        "GEMINI_API_KEY=first-key\nGEMINI_MODEL=gemini-first\n",
        encoding="utf-8",
    )
    (second_root / ".env").write_text(
        "GEMINI_API_KEY=second-key\nGEMINI_MODEL=gemini-second\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    first_settings = Settings.from_env(project_root=first_root)
    second_settings = Settings.from_env(project_root=second_root)

    assert first_settings.gemini_api_key == "first-key"
    assert first_settings.gemini_model == "gemini-first"
    assert second_settings.gemini_api_key == "second-key"
    assert second_settings.gemini_model == "gemini-second"


def test_ensure_dirs_creates_runtime_directories(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)

    settings.ensure_dirs()

    assert settings.logs_dir.is_dir()
    assert settings.rag_dir.is_dir()
    assert settings.eval_dir.is_dir()
    assert settings.figures_dir.is_dir()
