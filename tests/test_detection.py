import json
from datetime import datetime, timezone

import pytest

from aiops_agent.data.generator import generate_logs
from aiops_agent.detection.ewma import ewma
from aiops_agent.detection.zscore import z_scores
from aiops_agent.detection.windows import aggregate_windows
from aiops_agent.services.log_service import LogService
from aiops_agent.services.detection_service import DetectionConfig, DetectionService


def _record(
    *,
    timestamp: datetime,
    service: str = "api-gateway",
    latency_ms: float = 100.0,
    status_code: int = 200,
    error_code: str = "NONE",
    queue_depth: int = 10,
    anomaly_type: str = "normal",
    is_anomaly: bool = False,
):
    from aiops_agent.models.schemas import LogRecord

    return LogRecord(
        timestamp=timestamp,
        service=service,
        latency_ms=latency_ms,
        error_code=error_code,
        request_id=f"req-{service}-{int(timestamp.timestamp())}",
        endpoint="/orders",
        status_code=status_code,
        cpu_pct=35.0,
        memory_mb=512.0,
        queue_depth=queue_depth,
        dependency="data-service",
        anomaly_type=anomaly_type,
        is_anomaly=is_anomaly,
    )


def test_ewma_responds_to_recent_values():
    values = [10.0, 10.0, 10.0, 100.0]
    slow = ewma(values, alpha=0.1)
    fast = ewma(values, alpha=0.3)

    assert fast[-1] > slow[-1]


def test_ewma_handles_empty_values_and_invalid_alpha():
    assert ewma([], alpha=0.2) == []

    with pytest.raises(ValueError):
        ewma([1.0], alpha=0.0)
    with pytest.raises(ValueError):
        ewma([1.0], alpha=1.1)


def test_z_scores_flags_spike():
    scores = z_scores([10.0, 11.0, 9.0, 10.5, 80.0])
    assert scores[-1] > 2.0


def test_z_scores_handles_short_and_zero_variance_series():
    assert z_scores([]) == []
    assert z_scores([5.0]) == [0.0]
    assert z_scores([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]

    scores = z_scores([0.0, 0.0, 0.0, 100.0])
    assert scores[-1] > 2.0


def test_aggregate_windows_preserves_anomaly_labels():
    records = generate_logs(seed=5, per_service=80)
    windows = aggregate_windows(records, window_seconds=10)
    assert any(window.is_anomaly for window in windows)
    assert any("latency_spike" in window.anomaly_types for window in windows)


def test_aggregate_windows_validates_window_and_computes_metrics():
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    records = [
        _record(timestamp=base_time, latency_ms=100.0, queue_depth=10),
        _record(
            timestamp=base_time,
            latency_ms=200.0,
            status_code=504,
            error_code="UPSTREAM_TIMEOUT",
            queue_depth=20,
            anomaly_type="latency_spike",
            is_anomaly=True,
        ),
        _record(timestamp=base_time, service="auth-service", latency_ms=50.0),
    ]

    with pytest.raises(ValueError):
        aggregate_windows(records, window_seconds=0)

    windows = aggregate_windows(records, window_seconds=10)
    target = next(window for window in windows if window.service == "api-gateway")

    assert target.latency_mean == 150.0
    assert target.latency_p95 == 195.0
    assert target.error_rate == 0.5
    assert target.queue_depth_mean == 15.0
    assert target.is_anomaly is True
    assert target.anomaly_types == ("latency_spike",)


def test_detection_service_finds_known_anomalies():
    records = generate_logs(seed=11, per_service=220)
    service = DetectionService(DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10))
    anomalies = service.detect(records)

    assert anomalies
    assert {item.anomaly_type for item in anomalies} & {"latency_spike", "transaction_conflict", "queue_backlog"}


def test_detection_config_validates_thresholds():
    with pytest.raises(ValueError):
        DetectionConfig(alpha=0.0)
    with pytest.raises(ValueError):
        DetectionConfig(z_threshold=0.0)
    with pytest.raises(ValueError):
        DetectionConfig(window_seconds=0)


def test_incremental_detect_uses_buffered_records():
    records = generate_logs(seed=11, per_service=220)
    config = DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    incremental_service = DetectionService(config)
    batch_service = DetectionService(config)

    incremental_service.incremental_detect(records[:300], flush_at=records[299].timestamp)
    incremental_anomalies = incremental_service.incremental_detect(records[300:])

    assert incremental_anomalies == batch_service.detect(records)


def test_log_service_read_jsonl_limit_and_false_string(tmp_path):
    first = _record(timestamp=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc))
    second = first.to_json_dict() | {
        "request_id": "req-api-gateway-false",
        "is_anomaly": "false",
    }
    path = tmp_path / "logs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(first.to_json_dict()),
                json.dumps(second),
            ]
        ),
        encoding="utf-8",
    )

    limited = LogService().read_jsonl(path, limit=1)
    records = LogService().read_jsonl(path)

    assert len(limited) == 1
    assert records[1].is_anomaly is False
