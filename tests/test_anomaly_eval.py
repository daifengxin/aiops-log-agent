import pytest

from aiops_agent.data.generator import generate_logs
from aiops_agent.evaluation.anomaly_eval import (
    evaluate_parameter_grid,
    evaluate_windows_by_type,
)
from aiops_agent.evaluation.metrics import classification_metrics, recall_at_k


def test_classification_metrics_values():
    metrics = classification_metrics(
        true_labels=[True, True, False, False],
        pred_labels=[True, False, True, False],
    )

    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5


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
