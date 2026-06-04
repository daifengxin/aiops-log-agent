from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import numpy as np

from aiops_agent.data.schemas import LogRecord, WindowMetric


def aggregate_windows(
    records: list[LogRecord],
    window_seconds: int,
) -> list[WindowMetric]:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0")

    grouped: dict[tuple[str, int], list[LogRecord]] = defaultdict(list)
    for record in records:
        epoch = int(record.timestamp.timestamp())
        bucket_epoch = (epoch // window_seconds) * window_seconds
        grouped[(record.service, bucket_epoch)].append(record)

    windows: list[WindowMetric] = []
    for (service, bucket_epoch), bucket_records in grouped.items():
        latencies = np.array([item.latency_ms for item in bucket_records], dtype=float)
        queue_depths = np.array(
            [item.queue_depth for item in bucket_records],
            dtype=float,
        )
        errors = [
            item
            for item in bucket_records
            if item.status_code >= 400 or item.error_code != "NONE"
        ]
        tzinfo = bucket_records[0].timestamp.tzinfo

        # 保留窗口内任意异常标签，方便检测服务输出可解释的异常类型。
        anomaly_types = sorted(
            {
                item.anomaly_type
                for item in bucket_records
                if item.is_anomaly and item.anomaly_type != "normal"
            }
        )
        is_anomaly = any(item.is_anomaly for item in bucket_records)
        windows.append(
            WindowMetric(
                service=service,
                window_seconds=window_seconds,
                bucket_start=datetime.fromtimestamp(bucket_epoch, tz=tzinfo),
                latency_mean=float(np.mean(latencies)),
                latency_p95=float(np.percentile(latencies, 95)),
                error_rate=len(errors) / len(bucket_records),
                queue_depth_mean=float(np.mean(queue_depths)),
                is_anomaly=is_anomaly,
                anomaly_types=tuple(anomaly_types),
            )
        )

    # 固定排序让检测结果和测试在不同运行中保持稳定。
    return sorted(windows, key=lambda item: (item.service, item.bucket_start))
