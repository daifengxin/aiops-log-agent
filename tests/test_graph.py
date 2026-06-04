from aiops_agent.data.generator import generate_logs
from aiops_agent.graph.builder import build_diagnosis_graph
from aiops_agent.graph.nodes import DiagnosisGraphNodes
from aiops_agent.models.schemas import RetrievedChunk
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
    assert any(item.level == "SAFE" for item in result["safe_commands"])
    assert any(item.level == "CAUTION" for item in result["safe_commands"])
    assert any(item.level == "DANGER" for item in result["blocked_commands"])
    assert all(item.level != "CAUTION" for item in result["blocked_commands"])
    assert result["alert_decision"]
    assert "suppressed" in result["alert_decision"]


def test_suppress_alerts_without_anomaly_does_not_mark_suppressed():
    nodes = DiagnosisGraphNodes(
        llm_service=FakeLLMService(),
        rag_service=FakeRAGService(),
    )

    result = nodes.suppress_alerts({"detected_anomalies": []})

    assert result["alert_decision"]["suppressed"] is False
    assert result["alert_decision"]["reason"] == "no_detected_anomaly"
