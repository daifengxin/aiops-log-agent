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
    assert "异常类型识别准确性" in report
    assert "RAG Chunking Recall@5" in report
    assert "命令安全分级" in report
    assert "60 秒内相同 service + anomaly_type + root_cause" in report
    assert "10 倍日志量扩容" in report


def test_write_full_report_creates_required_figures_and_eval_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)

    write_full_report(settings)

    expected_figures = {
        "f1_heatmap.png",
        "anomaly_threshold_f1.png",
        "anomaly_window_f1.png",
        "rag_recall_at_5.png",
        "safety_confusion_matrix.png",
    }
    actual_figures = {path.name for path in settings.figures_dir.iterdir()}
    assert expected_figures <= actual_figures

    expected_artifacts = {
        "generated_logs.jsonl",
        "rag_queries.json",
        "anomaly_grid.json",
        "window_f1.json",
        "type_f1.json",
        "rag_recall.json",
        "safety_eval.json",
        "alert_suppression.json",
    }
    actual_artifacts = {path.name for path in settings.eval_dir.iterdir()}
    assert expected_artifacts <= actual_artifacts


def test_write_full_report_mentions_corpus_scale_and_alert_reduction(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)

    write_full_report(settings)

    report = (tmp_path / "reports" / "evaluation.md").read_text(encoding="utf-8")
    assert "Kubernetes 官方语料清单" in report
    assert "估算页数" in report
    assert "≥ 50 页" in report
    assert "安全混淆矩阵" in report
    assert "告警降噪率" in report
