from __future__ import annotations

from datetime import datetime

from aiops_agent.detection.windows import aggregate_windows
from aiops_agent.evaluation.metrics import classification_metrics
from aiops_agent.models.schemas import DetectedAnomaly, LogRecord, WindowMetric
from aiops_agent.services.detection_service import DetectionConfig, DetectionService

TARGET_ANOMALY_TYPES = ("latency_spike", "transaction_conflict")
ALL_ANOMALY_TYPES = ("latency_spike", "transaction_conflict", "queue_backlog")
WindowKey = tuple[str, int, datetime]


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
            predicted_keys = _detected_window_keys(
                windows=windows,
                alpha=alpha,
                threshold=threshold,
                window_seconds=window_seconds,
            )
            metrics = _metrics_for_windows(
                windows=windows,
                predicted_keys=predicted_keys,
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
        predicted_keys = _detected_window_keys(
            windows=window_metrics,
            alpha=alpha,
            threshold=threshold,
            window_seconds=window_seconds,
        )
        for anomaly_type in TARGET_ANOMALY_TYPES:
            metrics = _metrics_for_windows(
                windows=window_metrics,
                predicted_keys=predicted_keys,
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


def evaluate_type_classification(
    records: list[LogRecord],
    alpha: float,
    threshold: float,
    window_seconds: int,
) -> list[dict[str, float | int | str]]:
    windows = aggregate_windows(records, window_seconds)
    predicted_types = _detected_window_types(
        windows=windows,
        alpha=alpha,
        threshold=threshold,
        window_seconds=window_seconds,
    )

    rows: list[dict[str, float | int | str]] = []
    for anomaly_type in ALL_ANOMALY_TYPES:
        true_labels = [
            anomaly_type in window.anomaly_types
            for window in windows
        ]
        pred_labels = [
            anomaly_type in predicted_types.get(_window_key(window), set())
            for window in windows
        ]
        rows.append(
            {
                "window_seconds": window_seconds,
                "anomaly_type": anomaly_type,
                "alpha": alpha,
                "z_threshold": threshold,
                **classification_metrics(
                    true_labels=true_labels,
                    pred_labels=pred_labels,
                ),
            }
        )

    return rows


def _detected_window_keys(
    windows: list[WindowMetric],
    alpha: float,
    threshold: float,
    window_seconds: int,
) -> set[WindowKey]:
    # 即使没有聚合窗口，也先构造配置，保证参数校验语义一致。
    config = DetectionConfig(
        alpha=alpha,
        z_threshold=threshold,
        window_seconds=window_seconds,
    )
    if not windows:
        return set()

    anomalies = DetectionService(config=config).detect_from_windows(windows)
    return {_detected_window_key(item) for item in anomalies}


def _detected_window_types(
    windows: list[WindowMetric],
    alpha: float,
    threshold: float,
    window_seconds: int,
) -> dict[WindowKey, set[str]]:
    config = DetectionConfig(
        alpha=alpha,
        z_threshold=threshold,
        window_seconds=window_seconds,
    )
    if not windows:
        return {}

    detected: dict[WindowKey, set[str]] = {}
    for anomaly in DetectionService(config=config).detect_from_windows(windows):
        detected.setdefault(_detected_window_key(anomaly), set()).add(
            anomaly.anomaly_type
        )
    return detected


def _metrics_for_windows(
    windows: list[WindowMetric],
    predicted_keys: set[WindowKey],
    anomaly_type: str | None,
) -> dict[str, float]:
    # 类型行评估的是对应真值类型的窗口级覆盖率，预测侧复用全部已检测窗口。
    true_labels = [
        _is_target_window(window, anomaly_type)
        for window in windows
    ]
    pred_labels = [
        _window_key(window) in predicted_keys
        for window in windows
    ]

    return classification_metrics(true_labels=true_labels, pred_labels=pred_labels)


def _is_target_window(window: WindowMetric, anomaly_type: str | None) -> bool:
    if anomaly_type is None:
        return window.is_anomaly
    return anomaly_type in window.anomaly_types


def _window_key(window: WindowMetric) -> WindowKey:
    return (window.service, window.window_seconds, window.bucket_start)


def _detected_window_key(anomaly: DetectedAnomaly) -> WindowKey:
    return (anomaly.service, anomaly.window_seconds, anomaly.bucket_start)
