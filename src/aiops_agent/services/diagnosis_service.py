from __future__ import annotations

import json
from typing import Any

from aiops_agent.models.schemas import DetectedAnomaly, RetrievedChunk
from aiops_agent.services.llm_service import GeminiLLMService

REQUIRED_REPORT_KEYS = {
    "anomaly_type",
    "likely_root_causes",
    "evidence",
    "recommended_commands",
    "confidence",
}


class DiagnosisService:
    """把检测和 RAG 上下文组织成 Gemini 诊断报告。"""

    def __init__(self, llm_service: GeminiLLMService) -> None:
        self.llm_service = llm_service

    def diagnose(
        self,
        anomalies: list[DetectedAnomaly],
        chunks: list[RetrievedChunk],
    ) -> dict[str, Any]:
        report = self.llm_service.generate_json(self.build_prompt(anomalies, chunks))
        self._validate_report(report)
        return report

    def build_prompt(
        self,
        anomalies: list[DetectedAnomaly],
        chunks: list[RetrievedChunk],
    ) -> str:
        anomaly_rows = [item.model_dump(mode="json") for item in anomalies]
        chunk_rows = [item.model_dump(mode="json") for item in chunks]
        # 提示词固定输出 JSON，后续节点依赖 recommended_commands 做安全分级。
        return (
            "You are an AIOps diagnosis assistant. Return only JSON with keys "
            "anomaly_type, likely_root_causes, evidence, recommended_commands, confidence.\n"
            f"anomalies: {json.dumps(anomaly_rows, ensure_ascii=False)}\n"
            f"retrieved_chunks: {json.dumps(chunk_rows, ensure_ascii=False)}"
        )

    def _validate_report(self, report: dict[str, Any]) -> None:
        missing = REQUIRED_REPORT_KEYS - report.keys()
        if missing:
            raise ValueError(f"Gemini report missing required keys: {sorted(missing)}")
        for key in ("likely_root_causes", "evidence", "recommended_commands"):
            if not isinstance(report[key], list):
                raise ValueError(f"Gemini report field {key} must be a list")
        if not isinstance(report["confidence"], int | float):
            raise ValueError("Gemini report field confidence must be numeric")
