from aiops_agent.config import Settings
from aiops_agent.evaluation.report_writer import write_full_report


def test_write_full_report_creates_evaluation_markdown(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)

    write_full_report(settings)

    report_path = tmp_path / "reports" / "evaluation.md"
    assert report_path.is_file()
    report = report_path.read_text(encoding="utf-8")
    assert "异常检测参数敏感性" in report
    assert "RAG Chunking Recall@5" in report
    assert "命令安全分级" in report
    assert "10 倍日志量扩容" in report
