import json
import math
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


def _window(
    *,
    bucket_start: datetime,
    latency_p95: float,
    service: str = "api-gateway",
    error_rate: float = 0.0,
    queue_depth_mean: float = 10.0,
    anomaly_types: tuple[str, ...] = (),
):
    from aiops_agent.models.schemas import WindowMetric

    return WindowMetric(
        service=service,
        window_seconds=10,
        bucket_start=bucket_start,
        latency_mean=latency_p95,
        latency_p95=latency_p95,
        error_rate=error_rate,
        queue_depth_mean=queue_depth_mean,
        is_anomaly=bool(anomaly_types),
        anomaly_types=anomaly_types,
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
    assert z_scores([0.0, 100.0]) == [0.0, 0.0]
    assert z_scores([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]

    scores = z_scores([0.0, 0.0, 0.0, 100.0])
    assert math.isfinite(scores[-1])
    assert scores[-1] > 2.0
    assert z_scores([0.0, 0.0, 0.0, 5.0])[-1] < 2.0


def test_z_scores_only_scores_positive_spikes_after_warmup():
    assert z_scores([10.0, 10.0, 10.0, 5.0])[-1] == 0.0
    assert z_scores([10.0, 20.0, 30.0, 20.0])[-1] == 0.0
    assert z_scores([10.0, 10.0, 10.0, 10.0])[-1] == 0.0


@pytest.mark.parametrize(
    "values",
    [
        [-1.0, -1.0, -1.0, 0.0],
        [-10.0, -10.0, -10.0, -5.0],
    ],
)
def test_z_scores_ignore_nonpositive_residuals(values):
    assert z_scores(values)[-1] == 0.0


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


def test_detection_service_has_bounded_pre_spike_behavior():
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        _window(bucket_start=base_time.replace(second=offset), latency_p95=latency)
        for offset, latency in [(0, 100.0), (10, 100.0), (20, 100.0), (30, 220.0)]
    ]

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert [item.bucket_start for item in anomalies] == [base_time.replace(second=30)]


def test_detection_service_does_not_alert_on_latency_drop_recovery():
    from aiops_agent.models.schemas import WindowMetric

    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        WindowMetric(
            service="api-gateway",
            window_seconds=10,
            bucket_start=base_time,
            latency_mean=500.0,
            latency_p95=500.0,
            error_rate=0.0,
            queue_depth_mean=10.0,
            is_anomaly=False,
            anomaly_types=(),
        ),
        WindowMetric(
            service="api-gateway",
            window_seconds=10,
            bucket_start=base_time.replace(second=10),
            latency_mean=500.0,
            latency_p95=500.0,
            error_rate=0.0,
            queue_depth_mean=10.0,
            is_anomaly=False,
            anomaly_types=(),
        ),
        WindowMetric(
            service="api-gateway",
            window_seconds=10,
            bucket_start=base_time.replace(second=20),
            latency_mean=500.0,
            latency_p95=500.0,
            error_rate=0.0,
            queue_depth_mean=10.0,
            is_anomaly=False,
            anomaly_types=(),
        ),
        WindowMetric(
            service="api-gateway",
            window_seconds=10,
            bucket_start=base_time.replace(second=30),
            latency_mean=100.0,
            latency_p95=100.0,
            error_rate=0.0,
            queue_depth_mean=10.0,
            is_anomaly=False,
            anomaly_types=(),
        ),
    ]

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert anomalies == []
    assert all("exceeded EWMA baseline" not in item.reason for item in anomalies)


def test_detection_service_alerts_on_positive_spike_after_stable_history():
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        _window(bucket_start=base_time.replace(second=offset), latency_p95=latency)
        for offset, latency in [(0, 100.0), (10, 100.0), (20, 100.0), (30, 220.0)]
    ]

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert len(anomalies) == 1
    assert anomalies[0].bucket_start == base_time.replace(second=30)
    assert anomalies[0].score >= 2.0


def test_detection_service_extends_active_high_latency_period():
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        _window(bucket_start=base_time.replace(second=offset), latency_p95=latency)
        for offset, latency in [
            (0, 100.0),
            (10, 100.0),
            (20, 100.0),
            (30, 220.0),
            (40, 220.0),
            (50, 220.0),
            (59, 100.0),
        ]
    ]

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert [item.bucket_start for item in anomalies] == [
        base_time.replace(second=30),
        base_time.replace(second=40),
        base_time.replace(second=50),
    ]
    assert "active anomaly period" in anomalies[1].reason


def test_detection_service_infers_type_without_label_leakage():
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        _window(bucket_start=base_time.replace(second=offset), latency_p95=latency)
        for offset, latency in [(0, 100.0), (10, 100.0), (20, 100.0)]
    ]
    windows.append(
        _window(
            bucket_start=base_time.replace(second=30),
            latency_p95=220.0,
            anomaly_types=("queue_backlog",),
        )
    )

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert len(anomalies) == 1
    assert anomalies[0].anomaly_type == "latency_spike"


def test_detection_service_does_not_alert_when_positive_residual_declines():
    from aiops_agent.models.schemas import WindowMetric

    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    windows = [
        WindowMetric(
            service="api-gateway",
            window_seconds=10,
            bucket_start=base_time.replace(second=offset),
            latency_mean=latency,
            latency_p95=latency,
            error_rate=0.0,
            queue_depth_mean=10.0,
            is_anomaly=False,
            anomaly_types=(),
        )
        for offset, latency in [
            (0, 100.0),
            (10, 200.0),
            (20, 200.0),
            (30, 200.0),
            (40, 180.0),
        ]
    ]

    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10)
    ).detect_from_windows(windows)

    assert anomalies == []


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


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        (" TRUE ", True),
        ("False", False),
        (" false ", False),
    ],
)
def test_log_service_read_jsonl_parses_string_bool_values(
    tmp_path,
    raw_value,
    expected,
):
    record = _record(timestamp=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc))
    path = tmp_path / "logs.jsonl"
    path.write_text(
        json.dumps(record.to_json_dict() | {"is_anomaly": raw_value}),
        encoding="utf-8",
    )

    records = LogService().read_jsonl(path)

    assert records[0].is_anomaly is expected


@pytest.mark.parametrize("invalid_value", ["0", "yes", 1, None, ""])
def test_log_service_read_jsonl_rejects_invalid_bool_values(tmp_path, invalid_value):
    record = _record(timestamp=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc))
    path = tmp_path / "logs.jsonl"
    path.write_text(
        json.dumps(record.to_json_dict() | {"is_anomaly": invalid_value}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        LogService().read_jsonl(path)


def test_log_service_read_jsonl_rejects_unknown_fields(tmp_path):
    record = _record(timestamp=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc))
    path = tmp_path / "logs.jsonl"
    path.write_text(
        json.dumps(record.to_json_dict() | {"unexpected": "value"}),
        encoding="utf-8",
    )

    with pytest.raises((ValidationError, ValueError)):
        LogService().read_jsonl(path)
