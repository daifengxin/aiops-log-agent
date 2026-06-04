from __future__ import annotations

from aiops_agent.detection.windows import aggregate_windows
from aiops_agent.evaluation.metrics import classification_metrics
from aiops_agent.models.schemas import LogRecord, WindowMetric
from aiops_agent.services.detection_service import DetectionConfig, DetectionService

TARGET_ANOMALY_TYPES = ("latency_spike", "transaction_conflict")


def evaluate_parameter_grid(
    records: list[LogRecord],
    alphas: list[float],
    thresholds: list[float],
    window_seconds: int,
) -> list[dict[str, float]]:
    windows = aggregate_windows(records, window_seconds)
    rows: list[dict[str, float]] = []

    for alpha in alphas:
        for threshold in thresholds:
            metrics = _evaluate_windows(
                windows=windows,
                alpha=alpha,
                threshold=threshold,
                anomaly_type=None,
            )
            rows.append(
                {
                    "alpha": alpha,
                    "z_threshold": threshold,
                    **metrics,
                }
            )

    return rows


def evaluate_windows_by_type(
    records: list[LogRecord],
    alpha: float,
    threshold: float,
    windows: list[int],
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []

    for window_seconds in windows:
        window_metrics = aggregate_windows(records, window_seconds)
        for anomaly_type in TARGET_ANOMALY_TYPES:
            metrics = _evaluate_windows(
                windows=window_metrics,
                alpha=alpha,
                threshold=threshold,
                anomaly_type=anomaly_type,
            )
            rows.append(
                {
                    "window_seconds": window_seconds,
                    "anomaly_type": anomaly_type,
                    "alpha": alpha,
                    "z_threshold": threshold,
                    **metrics,
                }
            )

    return rows


def _evaluate_windows(
    windows: list[WindowMetric],
    alpha: float,
    threshold: float,
    anomaly_type: str | None,
) -> dict[str, float]:
    if not windows:
        return classification_metrics(true_labels=[], pred_labels=[])

    config = DetectionConfig(
        alpha=alpha,
        z_threshold=threshold,
        window_seconds=windows[0].window_seconds,
    )
    anomalies = DetectionService(config=config).detect_from_windows(windows)

    # 类型行评估的是对应真值类型的窗口级覆盖率，预测侧使用全部已检测窗口。
    predicted_keys = {
        (item.service, item.bucket_start)
        for item in anomalies
    }
    true_labels = [
        _is_target_window(window, anomaly_type)
        for window in windows
    ]
    pred_labels = [
        (window.service, window.bucket_start) in predicted_keys
        for window in windows
    ]

    return classification_metrics(true_labels=true_labels, pred_labels=pred_labels)


def _is_target_window(window: WindowMetric, anomaly_type: str | None) -> bool:
    if anomaly_type is None:
        return window.is_anomaly
    return anomaly_type in window.anomaly_types
