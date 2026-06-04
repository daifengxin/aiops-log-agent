from __future__ import annotations

import numpy as np


def z_scores(values: list[float]) -> list[float]:
    """基于历史值计算绝对 z-score，用于突出相对近期基线的尖峰。"""

    if len(values) < 2:
        return [0.0 for _ in values]

    scores = [0.0]
    for index in range(1, len(values)):
        history = np.array(values[:index], dtype=float)
        std = float(np.std(history))
        if std == 0.0:
            scores.append(0.0)
            continue

        mean = float(np.mean(history))
        scores.append(abs((float(values[index]) - mean) / std))
    return scores
