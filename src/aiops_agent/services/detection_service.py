from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from aiops_agent.models.schemas import DetectedAnomaly, LogRecord, WindowMetric
from aiops_agent.detection.ewma import ewma
from aiops_agent.detection.windows import aggregate_windows
from aiops_agent.detection.zscore import z_scores


@dataclass(frozen=True)
class DetectionConfig:
    alpha: float = 0.2
    z_threshold: float = 2.5
    window_seconds: int = 10

    def __post_init__(self) -> None:
        if not 0 < self.alpha <= 1:
            raise ValueError("alpha must be greater than 0 and less than or equal to 1")
        if self.z_threshold <= 0:
            raise ValueError("z_threshold must be greater than 0")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")


@dataclass
class DetectionService:
    config: DetectionConfig = field(default_factory=DetectionConfig)
    _stream_buffer: list[LogRecord] = field(default_factory=list)

    def detect(self, records: list[LogRecord]) -> list[DetectedAnomaly]:
        windows = aggregate_windows(records, self.config.window_seconds)
        return self.detect_from_windows(windows)

    def detect_from_windows(
        self,
        windows: list[WindowMetric],
    ) -> list[DetectedAnomaly]:
        by_service: dict[str, list[WindowMetric]] = defaultdict(list)
        for window in windows:
            by_service[window.service].append(window)

        anomalies: list[DetectedAnomaly] = []
        for service_windows in by_service.values():
            ordered = sorted(service_windows, key=lambda item: item.bucket_start)
            latencies = [window.latency_p95 for window in ordered]
            baseline = ewma(latencies, self.config.alpha)
            residuals = [
                latency - expected
                for latency, expected in zip(latencies, baseline, strict=True)
            ]
            scores = z_scores(residuals)

            for window, score, expected in zip(ordered, scores, baseline, strict=True):
                # 延迟异常只关心高于基线的尖峰，恢复/下降窗口不应触发报警。
                if window.latency_p95 <= expected or score < self.config.z_threshold:
                    continue

                anomaly_type = self._infer_anomaly_type(window)
                anomalies.append(
                    DetectedAnomaly(
                        service=window.service,
                        window_seconds=window.window_seconds,
                        bucket_start=window.bucket_start,
                        score=float(score),
                        metric_name="latency_p95",
                        anomaly_type=anomaly_type,
                        reason=(
                            f"latency_p95={window.latency_p95:.2f} exceeded "
                            f"EWMA baseline={expected:.2f}"
                        ),
                    )
                )

        return sorted(anomalies, key=lambda item: (item.bucket_start, item.service))

    def incremental_detect(
        self,
        new_records: list[LogRecord],
        flush_at: object | None = None,
    ) -> list[DetectedAnomaly]:
        """追加新日志并基于完整缓冲区重算，flush_at 仅保留给后续流式切窗。"""

        _ = flush_at
        self._stream_buffer.extend(new_records)
        return self.detect(self._stream_buffer)

    def _infer_anomaly_type(self, window: WindowMetric) -> str:
        if window.anomaly_types:
            return window.anomaly_types[0]

        # 无人工标签时，用高队列和高错误率做轻量解释；剩余高延迟视为延迟尖峰。
        if window.queue_depth_mean >= 100.0:
            return "queue_backlog"
        if window.error_rate >= 0.2:
            return "transaction_conflict"
        return "latency_spike"
