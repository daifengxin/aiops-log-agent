from __future__ import annotations


def classification_metrics(
    true_labels: list[bool],
    pred_labels: list[bool],
) -> dict[str, float]:
    if len(true_labels) != len(pred_labels):
        raise ValueError("true_labels and pred_labels must have the same length")

    tp = fp = fn = tn = 0
    for actual, predicted in zip(true_labels, pred_labels):
        if actual and predicted:
            tp += 1
        elif not actual and predicted:
            fp += 1
        elif actual and not predicted:
            fn += 1
        else:
            tn += 1

    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    false_positive_rate = _safe_divide(fp, fp + tn)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(false_positive_rate, 4),
    }


def recall_at_k(
    expected_ids: set[str],
    retrieved_ids: list[str],
    k: int = 5,
) -> float:
    if not expected_ids or k <= 0:
        return 0.0

    top_k_ids = set(retrieved_ids[:k])
    return round(len(expected_ids & top_k_ids) / len(expected_ids), 4)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
