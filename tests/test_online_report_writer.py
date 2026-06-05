import json

from aiops_agent.config import Settings
from aiops_agent.data.generator import generate_logs
from aiops_agent.evaluation.online_report_writer import (
    sample_online_eval_records,
    write_online_gemini_report,
)


class FakeAppendixLLM:
    def __init__(self) -> None:
        self.prompt = ""

    def generate_json(self, prompt: str):
        self.prompt = prompt
        return {
            "quantitative_appendix_markdown": (
                "## 量化评估附录（Gemini 生成）\n\n"
                "Gemini 根据在线评估指标生成了参数敏感性、窗口粒度、RAG、命令安全"
                "和优化前后对比分析。"
            )
        }


def test_sample_online_eval_records_uses_200_normal_and_40_target_anomalies():
    records = generate_logs(seed=42, per_service=220)

    sample = sample_online_eval_records(records)

    normal_count = sum(1 for record in sample if not record.is_anomaly)
    anomaly_count = sum(1 for record in sample if record.is_anomaly)
    anomaly_types = {record.anomaly_type for record in sample if record.is_anomaly}

    assert len(sample) == 240
    assert normal_count == 200
    assert anomaly_count == 40
    assert anomaly_types == {"latency_spike", "transaction_conflict"}


def test_write_online_gemini_report_calls_llm_and_writes_evidence(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    settings = Settings.from_env(project_root=tmp_path)
    fake_llm = FakeAppendixLLM()

    write_online_gemini_report(settings=settings, llm_service=fake_llm)

    report = (tmp_path / "reports" / "gemini_evaluation.md").read_text(
        encoding="utf-8"
    )
    artifact = json.loads(
        (tmp_path / "data" / "eval" / "online_gemini_evaluation.json").read_text(
            encoding="utf-8"
        )
    )

    assert "量化评估附录（Gemini 生成）" in report
    assert "200 normal + 40 anomaly" in report
    assert artifact["sample_counts"] == {
        "normal": 200,
        "anomaly": 40,
        "latency_spike": 20,
        "transaction_conflict": 20,
    }
    assert len(artifact["anomaly_grid"]) == 9
    assert len(artifact["window_rows"]) == 6
    assert len(artifact["rag_rows"]) == 2
    assert len(artifact["safety_rows"]) >= 20
    assert "kubectl get pods \\| dd of=/tmp/out" in report
    assert "anomaly_grid" in fake_llm.prompt
    assert "哪种粒度更适合哪类异常" in fake_llm.prompt
    assert "optimization_comparison" in fake_llm.prompt
