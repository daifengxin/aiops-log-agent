from __future__ import annotations


def ewma(values: list[float], alpha: float) -> list[float]:
    """计算 EWMA 序列；alpha 越大，越快响应最近的观测值。"""

    if not 0 < alpha <= 1:
        raise ValueError("alpha must be greater than 0 and less than or equal to 1")
    if not values:
        return []

    smoothed = [float(values[0])]
    for current in values[1:]:
        previous = smoothed[-1]
        smoothed.append(alpha * float(current) + (1 - alpha) * previous)
    return smoothed
