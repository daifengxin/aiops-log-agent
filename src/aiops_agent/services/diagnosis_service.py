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
        self._normalize_report(report)
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
            "anomaly_type, likely_root_causes, evidence, recommended_commands, confidence. "
            "likely_root_causes, evidence, and recommended_commands must be JSON arrays of strings. "
            "confidence must be a JSON number from 0 to 1, not a string or percent.\n"
            f"anomalies: {json.dumps(anomaly_rows, ensure_ascii=False)}\n"
            f"retrieved_chunks: {json.dumps(chunk_rows, ensure_ascii=False)}"
        )

    def _normalize_report(self, report: dict[str, Any]) -> None:
        confidence = report.get("confidence")
        if isinstance(confidence, str):
            value = confidence.strip()
            if value.endswith("%"):
                report["confidence"] = float(value.removesuffix("%").strip()) / 100
                return
            report["confidence"] = float(value)
        for key in ("likely_root_causes", "evidence"):
            # Gemini 偶尔会把单条原因/证据返回为字符串；这里安全地归一化为单元素数组。
            if isinstance(report.get(key), str):
                report[key] = [report[key]]

    def _validate_report(self, report: dict[str, Any]) -> None:
        missing = REQUIRED_REPORT_KEYS - report.keys()
        if missing:
            raise ValueError(f"Gemini report missing required keys: {sorted(missing)}")
        for key in ("likely_root_causes", "evidence", "recommended_commands"):
            if not isinstance(report[key], list):
                raise ValueError(f"Gemini report field {key} must be a list")
        if not all(isinstance(command, str) for command in report["recommended_commands"]):
            raise ValueError(
                "Gemini report field recommended_commands must contain only strings"
            )
        if not isinstance(report["confidence"], int | float):
            raise ValueError("Gemini report field confidence must be numeric")
