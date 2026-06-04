from __future__ import annotations

from typing import Any

from aiops_agent.graph.state import AIOpsDiagnosisState
from aiops_agent.services.alert_service import AlertService
from aiops_agent.services.detection_service import DetectionService
from aiops_agent.services.diagnosis_service import DiagnosisService
from aiops_agent.services.llm_service import GeminiLLMService
from aiops_agent.services.rag_service import RAGService
from aiops_agent.services.safety_service import CommandSafetyService


class DiagnosisGraphNodes:
    """LangGraph 节点适配层，节点只编排服务调用，不承载业务算法。"""

    def __init__(
        self,
        *,
        llm_service: GeminiLLMService | None = None,
        rag_service: RAGService | None = None,
    ) -> None:
        self.detection_service = DetectionService()
        self.rag_service = rag_service or RAGService()
        self.diagnosis_service = DiagnosisService(llm_service or GeminiLLMService())
        self.safety_service = CommandSafetyService()
        self.alert_service = AlertService()

    def detect(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        return {"detected_anomalies": self.detection_service.detect(state["records"])}

    def build_rag_query(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        query = self.rag_service.build_query(state.get("detected_anomalies", []))
        return {"rag_query": query}

    def retrieve_k8s_docs(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        chunks = self.rag_service.retrieve(state.get("rag_query", ""), top_k=5)
        return {"retrieved_chunks": chunks}

    def gemini(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        report = self.diagnosis_service.diagnose(
            state.get("detected_anomalies", []),
            state.get("retrieved_chunks", []),
        )
        return {"llm_report": report}

    def classify_commands(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        commands = state.get("llm_report", {}).get("recommended_commands", [])
        results = self.safety_service.classify_many([str(command) for command in commands])
        # SAFE 可直接执行，CAUTION 留在安全侧供人工复核；只有 DANGER 进入阻断列表。
        safe = [item for item in results if item.level in {"SAFE", "CAUTION"}]
        blocked = [item for item in results if item.level == "DANGER"]
        return {"safe_commands": safe, "blocked_commands": blocked}

    def suppress_alerts(self, state: AIOpsDiagnosisState) -> dict[str, Any]:
        anomalies = state.get("detected_anomalies", [])
        root_causes = state.get("llm_report", {}).get("likely_root_causes", [])
        if not anomalies:
            return {"alert_decision": {"suppressed": False, "reason": "no_detected_anomaly"}}

        root_cause = str(root_causes[0]) if root_causes else "unknown"
        return {
            "alert_decision": self.alert_service.evaluate(
                anomalies[0],
                root_cause=root_cause,
            )
        }
