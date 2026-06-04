from datetime import datetime, timezone

import pytest

from aiops_agent.data.generator import generate_logs
from aiops_agent.graph.builder import build_diagnosis_graph
from aiops_agent.graph.nodes import DiagnosisGraphNodes
from aiops_agent.models.schemas import DetectedAnomaly, RetrievedChunk
from aiops_agent.services.diagnosis_service import DiagnosisService
from aiops_agent.services.llm_service import GeminiLLMService


class FakeLLMService(GeminiLLMService):
    def __init__(self) -> None:
        pass

    def generate_json(self, prompt: str) -> dict:
        assert "anomalies" in prompt
        return {
            "anomaly_type": "latency_spike",
            "likely_root_causes": ["pod_cpu_saturation"],
            "evidence": ["api-gateway latency p95 exceeded EWMA baseline"],
            "recommended_commands": [
                "kubectl get pods -n prod",
                "kubectl rollout restart deployment/api",
                "kubectl delete pod bad-pod -n prod",
            ],
            "confidence": 0.82,
        }


class FakeInvalidCommandLLMService(GeminiLLMService):
    def __init__(self) -> None:
        pass

    def generate_json(self, prompt: str) -> dict:
        return {
            "anomaly_type": "latency_spike",
            "likely_root_causes": ["pod_cpu_saturation"],
            "evidence": ["api-gateway latency p95 exceeded EWMA baseline"],
            "recommended_commands": [123],
            "confidence": 0.82,
        }


class FakeRAGService:
    def build_query(self, anomalies):
        assert anomalies
        return "api-gateway latency kubernetes troubleshooting"

    def retrieve(self, query: str, top_k: int = 5):
        assert "kubernetes" in query
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                title="Debug Pods",
                text="Use kubectl get pods and kubectl describe pod for read-only triage.",
                source="fake",
                score=0.91,
            )
        ]


def test_diagnosis_graph_uses_fake_llm_and_classifies_commands(monkeypatch):
    monkeypatch.setattr("aiops_agent.graph.nodes.RAGService", FakeRAGService)
    records = generate_logs()

    result = build_diagnosis_graph(llm_service=FakeLLMService()).invoke(
        {"records": records[:260]}
    )

    assert result["llm_report"]["confidence"] == 0.82
    assert [item.level for item in result["safe_commands"]] == ["SAFE"]
    assert [item.level for item in result["review_commands"]] == ["CAUTION"]
    assert [item.level for item in result["blocked_commands"]] == ["DANGER"]
    assert all(item.level != "CAUTION" for item in result["safe_commands"])
    assert all(item.level != "CAUTION" for item in result["blocked_commands"])
    assert result["alert_decision"]
    assert "suppressed" in result["alert_decision"]


def test_building_graph_with_fake_llm_does_not_construct_default_rag(monkeypatch):
    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("RAGService should be constructed lazily")

    monkeypatch.setattr("aiops_agent.graph.nodes.RAGService", fail_if_constructed)

    build_diagnosis_graph(llm_service=FakeLLMService())


def test_diagnosis_service_rejects_non_string_recommended_commands():
    service = DiagnosisService(FakeInvalidCommandLLMService())

    with pytest.raises(ValueError, match="recommended_commands"):
        service.diagnose([], [])


def test_alert_suppression_state_persists_within_compiled_graph(monkeypatch):
    monkeypatch.setattr("aiops_agent.graph.nodes.RAGService", FakeRAGService)
    graph = build_diagnosis_graph(llm_service=FakeLLMService())
    records = generate_logs()[:260]

    first = graph.invoke({"records": records})
    second = graph.invoke({"records": records})

    assert first["alert_decision"]["suppressed"] is False
    assert second["alert_decision"]["suppressed"] is True


def test_suppress_alerts_uses_latest_detected_anomaly():
    nodes = DiagnosisGraphNodes(
        llm_service=FakeLLMService(),
        rag_service=FakeRAGService(),
    )
    first = DetectedAnomaly(
        service="api-gateway",
        window_seconds=10,
        bucket_start=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
        score=3.1,
        metric_name="latency_p95",
        anomaly_type="latency_spike",
        reason="first",
    )
    latest = DetectedAnomaly(
        service="api-gateway",
        window_seconds=10,
        bucket_start=datetime(2026, 6, 5, 9, 5, tzinfo=timezone.utc),
        score=3.8,
        metric_name="latency_p95",
        anomaly_type="latency_spike",
        reason="latest",
    )

    result = nodes.suppress_alerts(
        {
            "detected_anomalies": [first, latest],
            "llm_report": {"likely_root_causes": ["pod_cpu_saturation"]},
        }
    )

    assert result["alert_decision"]["bucket_start"] == latest.bucket_start


def test_suppress_alerts_without_anomaly_does_not_mark_suppressed():
    nodes = DiagnosisGraphNodes(
        llm_service=FakeLLMService(),
        rag_service=FakeRAGService(),
    )

    result = nodes.suppress_alerts({"detected_anomalies": []})

    assert result["alert_decision"]["suppressed"] is False
    assert result["alert_decision"]["reason"] == "no_detected_anomaly"
