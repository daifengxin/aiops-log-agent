from __future__ import annotations

from typing import Any, TypedDict

from aiops_agent.models.schemas import (
    DetectedAnomaly,
    LogRecord,
    RetrievedChunk,
    SafetyResult,
)


class AIOpsDiagnosisState(TypedDict, total=False):
    records: list[LogRecord]
    detected_anomalies: list[DetectedAnomaly]
    rag_query: str
    retrieved_chunks: list[RetrievedChunk]
    llm_report: dict[str, Any]
    safe_commands: list[SafetyResult]
    blocked_commands: list[SafetyResult]
    alert_decision: dict[str, Any]
    errors: list[str]
