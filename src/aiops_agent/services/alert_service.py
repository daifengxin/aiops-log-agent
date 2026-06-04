from __future__ import annotations

from datetime import datetime
from typing import Any

from aiops_agent.models.schemas import DetectedAnomaly


class AlertService:
    """按根因维度抑制短时间内重复告警。"""

    def __init__(self, suppression_seconds: int = 60) -> None:
        self.suppression_seconds = suppression_seconds
        self._last_alert_at: dict[tuple[str, str, str], datetime] = {}

    def evaluate(
        self,
        anomaly: DetectedAnomaly,
        root_cause: str,
    ) -> dict[str, Any]:
        key = (anomaly.service, anomaly.anomaly_type, root_cause)
        previous = self._last_alert_at.get(key)
        suppressed = False

        if previous is not None:
            elapsed = (anomaly.bucket_start - previous).total_seconds()
            suppressed = 0 <= elapsed < self.suppression_seconds

        # 只在实际发出告警时刷新时间戳，避免持续噪声把抑制窗口无限延长。
        if not suppressed:
            self._last_alert_at[key] = anomaly.bucket_start

        return {
            "service": anomaly.service,
            "anomaly_type": anomaly.anomaly_type,
            "root_cause": root_cause,
            "bucket_start": anomaly.bucket_start,
            "suppressed": suppressed,
        }
