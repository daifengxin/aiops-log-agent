from __future__ import annotations

import numpy as np

_MIN_HISTORY = 3


def z_scores(values: list[float]) -> list[float]:
    """基于历史值计算正向 z-score，只突出相对近期基线的上升尖峰。"""

    scores: list[float] = []
    for index, current in enumerate(values):
        if index < _MIN_HISTORY:
            scores.append(0.0)
            continue

        history = np.array(values[:index], dtype=float)
        mean = float(np.mean(history))
        if float(current) <= mean:
            scores.append(0.0)
            continue

        std = float(np.std(history))
        if std == 0.0:
            # warm-up 后历史完全平坦时，正向偏移是明确尖峰，直接给无穷大分数。
            scores.append(float("inf"))
            continue

        scores.append((float(current) - mean) / std)
    return scores
