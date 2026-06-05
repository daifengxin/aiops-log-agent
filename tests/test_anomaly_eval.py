from datetime import datetime, timezone

import pytest

from aiops_agent.data.generator import generate_logs
from aiops_agent.evaluation import anomaly_eval
from aiops_agent.evaluation.anomaly_eval import (
    evaluate_type_classification,
    evaluate_parameter_grid,
    evaluate_windows_by_type,
)
from aiops_agent.evaluation.metrics import classification_metrics, recall_at_k
from aiops_agent.models.schemas import DetectedAnomaly, WindowMetric


def test_classification_metrics_values():
    metrics = classification_metrics(
        true_labels=[True, True, False, False],
        pred_labels=[True, False, True, False],
    )

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5


@pytest.mark.parametrize(
    ("true_labels", "pred_labels", "expected"),
    [
        (
            [],
            [],
            {"precision": 0.0, "recall": 0.0, "f1": 0.0, "false_positive_rate": 0.0},
        ),
        (
            [False, False],
            [False, False],
            {"precision": 0.0, "recall": 0.0, "f1": 0.0, "false_positive_rate": 0.0},
        ),
        (
            [True, True],
            [False, False],
            {"precision": 0.0, "recall": 0.0, "f1": 0.0, "false_positive_rate": 0.0},
        ),
        (
            [True, True],
            [True, True],
            {"precision": 1.0, "recall": 1.0, "f1": 1.0, "false_positive_rate": 0.0},
        ),
        (
            [False, False],
            [True, True],
            {"precision": 0.0, "recall": 0.0, "f1": 0.0, "false_positive_rate": 1.0},
        ),
    ],
)
def test_classification_metrics_zero_denominator_edges(
    true_labels,
    pred_labels,
    expected,
):
    assert (
        classification_metrics(true_labels=true_labels, pred_labels=pred_labels)
        == expected
    )


def test_classification_metrics_rejects_length_mismatch():
    with pytest.raises(ValueError):
        classification_metrics(true_labels=[True], pred_labels=[True, False])


def test_recall_at_k_values():
    score = recall_at_k(
        expected_ids={"runbook-a", "runbook-b", "runbook-c"},
        retrieved_ids=["runbook-b", "runbook-x", "runbook-c"],
        k=2,
    )

    assert score == 0.3333


def test_parameter_grid_has_nine_rows():
    records = generate_logs(seed=17, per_service=220)
    rows = evaluate_parameter_grid(
        records,
        alphas=[0.1, 0.2, 0.3],
        thresholds=[2.0, 2.5, 3.0],
        window_seconds=10,
    )

    assert len(rows) == 9
    assert {
        "alpha",
        "z_threshold",
        "precision",
        "recall",
        "f1",
        "false_positive_rate",
    } <= set(rows[0])


def test_parameter_grid_handles_empty_records_with_valid_parameters():
    rows = evaluate_parameter_grid(
        records=[],
        alphas=[0.2],
        thresholds=[2.5],
        window_seconds=10,
    )

    assert rows == [
        {
            "alpha": 0.2,
            "z_threshold": 2.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
        }
    ]


@pytest.mark.parametrize(
    ("alphas", "thresholds", "window_seconds"),
    [
        ([0.0], [2.5], 10),
        ([0.2], [0.0], 10),
        ([0.2], [2.5], 0),
    ],
)
def test_parameter_grid_validates_parameters_for_empty_records(
    alphas,
    thresholds,
    window_seconds,
):
    with pytest.raises(ValueError):
        evaluate_parameter_grid(
            records=[],
            alphas=alphas,
            thresholds=thresholds,
            window_seconds=window_seconds,
        )


def test_window_eval_reports_target_types():
    records = generate_logs(seed=19, per_service=220)
    rows = evaluate_windows_by_type(
        records,
        alpha=0.2,
        threshold=2.5,
        windows=[1, 10, 60],
    )

    keys = {(row["window_seconds"], row["anomaly_type"]) for row in rows}
    assert (10, "latency_spike") in keys
    assert (60, "transaction_conflict") in keys


def test_window_eval_handles_empty_records_with_valid_parameters():
    rows = evaluate_windows_by_type(
        records=[],
        alpha=0.2,
        threshold=2.5,
        windows=[10],
    )

    assert rows == [
        {
            "window_seconds": 10,
            "anomaly_type": "latency_spike",
            "alpha": 0.2,
            "z_threshold": 2.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
        },
        {
            "window_seconds": 10,
            "anomaly_type": "transaction_conflict",
            "alpha": 0.2,
            "z_threshold": 2.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
        },
    ]


@pytest.mark.parametrize(
    ("alpha", "threshold", "windows"),
    [
        (0.0, 2.5, [10]),
        (0.2, 0.0, [10]),
        (0.2, 2.5, [0]),
    ],
)
def test_window_eval_validates_parameters_for_empty_records(
    alpha,
    threshold,
    windows,
):
    with pytest.raises(ValueError):
        evaluate_windows_by_type(
            records=[],
            alpha=alpha,
            threshold=threshold,
            windows=windows,
        )


def test_window_eval_detects_once_per_window_size(monkeypatch):
    bucket_start = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    target_window = WindowMetric(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        latency_mean=400.0,
        latency_p95=420.0,
        error_rate=0.0,
        queue_depth_mean=12.0,
        is_anomaly=True,
        anomaly_types=("latency_spike",),
    )
    calls = []

    monkeypatch.setattr(
        anomaly_eval,
        "aggregate_windows",
        lambda records, window_seconds: [target_window],
    )
    monkeypatch.setattr(
        anomaly_eval.DetectionService,
        "detect_from_windows",
        lambda self, windows: calls.append(windows) or [],
    )

    evaluate_windows_by_type(
        records=[],
        alpha=0.2,
        threshold=2.5,
        windows=[10],
    )

    assert len(calls) == 1


def test_window_type_metrics_count_detected_window_despite_inferred_type_mismatch(
    monkeypatch,
):
    bucket_start = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    target_window = WindowMetric(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        latency_mean=400.0,
        latency_p95=420.0,
        error_rate=0.0,
        queue_depth_mean=12.0,
        is_anomaly=True,
        anomaly_types=("latency_spike",),
    )
    detected_window = DetectedAnomaly(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        score=3.2,
        metric_name="latency_p95",
        anomaly_type="transaction_conflict",
        reason="detected same window with different inferred type",
    )

    monkeypatch.setattr(
        anomaly_eval,
        "aggregate_windows",
        lambda records, window_seconds: [target_window],
    )
    monkeypatch.setattr(
        anomaly_eval.DetectionService,
        "detect_from_windows",
        lambda self, windows: [detected_window],
    )

    rows = evaluate_windows_by_type(
        records=[],
        alpha=0.2,
        threshold=2.5,
        windows=[10],
    )
    latency_row = next(
        row for row in rows if row["anomaly_type"] == "latency_spike"
    )

    assert latency_row["precision"] == 1.0
    assert latency_row["recall"] == 1.0
    assert latency_row["f1"] == 1.0


def test_type_classification_metrics_penalize_inferred_type_mismatch(monkeypatch):
    bucket_start = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    target_window = WindowMetric(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        latency_mean=400.0,
        latency_p95=420.0,
        error_rate=0.0,
        queue_depth_mean=12.0,
        is_anomaly=True,
        anomaly_types=("latency_spike",),
    )
    detected_window = DetectedAnomaly(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        score=3.2,
        metric_name="latency_p95",
        anomaly_type="transaction_conflict",
        reason="detected same window with different inferred type",
    )

    monkeypatch.setattr(
        anomaly_eval,
        "aggregate_windows",
        lambda records, window_seconds: [target_window],
    )
    monkeypatch.setattr(
        anomaly_eval.DetectionService,
        "detect_from_windows",
        lambda self, windows: [detected_window],
    )

    rows = evaluate_type_classification(
        records=[],
        alpha=0.2,
        threshold=2.5,
        window_seconds=10,
    )
    latency_row = next(row for row in rows if row["anomaly_type"] == "latency_spike")
    conflict_row = next(
        row for row in rows if row["anomaly_type"] == "transaction_conflict"
    )

    assert latency_row["recall"] == 0.0
    assert latency_row["f1"] == 0.0
    assert conflict_row["precision"] == 0.0


def test_window_alignment_includes_window_seconds(monkeypatch):
    bucket_start = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    target_window = WindowMetric(
        service="api-gateway",
        window_seconds=10,
        bucket_start=bucket_start,
        latency_mean=400.0,
        latency_p95=420.0,
        error_rate=0.0,
        queue_depth_mean=12.0,
        is_anomaly=True,
        anomaly_types=("latency_spike",),
    )
    mismatched_detection = DetectedAnomaly(
        service="api-gateway",
        window_seconds=60,
        bucket_start=bucket_start,
        score=3.2,
        metric_name="latency_p95",
        anomaly_type="latency_spike",
        reason="same service and bucket at a different window size",
    )

    monkeypatch.setattr(
        anomaly_eval,
        "aggregate_windows",
        lambda records, window_seconds: [target_window],
    )
    monkeypatch.setattr(
        anomaly_eval.DetectionService,
        "detect_from_windows",
        lambda self, windows: [mismatched_detection],
    )

    rows = evaluate_windows_by_type(
        records=[],
        alpha=0.2,
        threshold=2.5,
        windows=[10],
    )
    latency_row = next(
        row for row in rows if row["anomaly_type"] == "latency_spike"
    )

    assert latency_row["precision"] == 0.0
    assert latency_row["recall"] == 0.0
    assert latency_row["f1"] == 0.0
