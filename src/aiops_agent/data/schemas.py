from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class LogRecord:
    """单条微服务日志，包含检测指标和人工标注字段。"""

    timestamp: datetime
    service: str
    latency_ms: float
    error_code: str
    request_id: str
    endpoint: str
    status_code: int
    cpu_pct: float
    memory_mb: float
    queue_depth: int
    dependency: str
    anomaly_type: str
    is_anomaly: bool

    def to_json_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["timestamp"] = self.timestamp.isoformat()
        return row


@dataclass(frozen=True)
class WindowMetric:
    """聚合后的时间窗口指标。"""

    service: str
    window_seconds: int
    bucket_start: datetime
    latency_mean: float
    latency_p95: float
    error_rate: float
    queue_depth_mean: float
    is_anomaly: bool
    anomaly_types: tuple[str, ...]


@dataclass(frozen=True)
class DetectedAnomaly:
    """检测器输出的异常窗口。"""

    service: str
    window_seconds: int
    bucket_start: datetime
    score: float
    metric_name: str
    anomaly_type: str
    reason: str


@dataclass(frozen=True)
class RetrievedChunk:
    """RAG 检索返回的文档片段。"""

    chunk_id: str
    title: str
    text: str
    source: str
    score: float


@dataclass(frozen=True)
class SafetyResult:
    """命令安全分级结果。"""

    command: str
    level: str
    reason: str
