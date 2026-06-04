from __future__ import annotations

import numpy as np

_MIN_HISTORY = 3
_MIN_STD = 10.0


def z_scores(values: list[float]) -> list[float]:
    """基于历史值计算正向 z-score，只突出相对近期基线的上升尖峰。"""

    scores: list[float] = []
    for index, current in enumerate(values):
        if index < _MIN_HISTORY:
            scores.append(0.0)
            continue

        if float(current) <= 0.0:
            scores.append(0.0)
            continue

        history = np.array(values[:index], dtype=float)
        mean = float(np.mean(history))
        if float(current) <= mean:
            scores.append(0.0)
            continue

        # 使用标准差下限，避免低方差场景产生 inf，同时保留 z-like 阈值语义。
        std = max(float(np.std(history)), _MIN_STD)
        scores.append((float(current) - mean) / std)
    return scores
