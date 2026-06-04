import json
import importlib.util
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from aiops_agent.data.generator import SERVICES, generate_logs, write_jsonl

EXPECTED_SERVICES = [
    "api-gateway",
    "auth-service",
    "business-service",
    "data-service",
    "message-queue",
]
EXPECTED_JSON_KEYS = {
    "timestamp",
    "service",
    "latency_ms",
    "error_code",
    "request_id",
    "endpoint",
    "status_code",
    "cpu_pct",
    "memory_mb",
    "queue_depth",
    "dependency",
    "anomaly_type",
    "is_anomaly",
}


def test_schema_models_live_under_models_and_are_pydantic():
    from aiops_agent.models.schemas import (
        DetectedAnomaly,
        LogRecord,
        RetrievedChunk,
        SafetyResult,
        WindowMetric,
    )

    assert importlib.util.find_spec("aiops_agent.data.schemas") is None
    for model in (LogRecord, WindowMetric, DetectedAnomaly, RetrievedChunk, SafetyResult):
        assert issubclass(model, BaseModel)
        assert model.model_config.get("frozen") is True
        assert model.model_config.get("extra") == "forbid"


def test_schema_models_reject_unknown_fields():
    from aiops_agent.models.schemas import (
        DetectedAnomaly,
        LogRecord,
        RetrievedChunk,
        SafetyResult,
        WindowMetric,
    )

    timestamp = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    samples = [
        (
            LogRecord,
            generate_logs(seed=3, per_service=1)[0].to_json_dict(),
        ),
        (
            WindowMetric,
            {
                "service": "api-gateway",
                "window_seconds": 10,
                "bucket_start": timestamp,
                "latency_mean": 100.0,
                "latency_p95": 120.0,
                "error_rate": 0.0,
                "queue_depth_mean": 10.0,
                "is_anomaly": False,
                "anomaly_types": (),
            },
        ),
        (
            DetectedAnomaly,
            {
                "service": "api-gateway",
                "window_seconds": 10,
                "bucket_start": timestamp,
                "score": 3.0,
                "metric_name": "latency_p95",
                "anomaly_type": "latency_spike",
                "reason": "test",
            },
        ),
        (
            RetrievedChunk,
            {
                "chunk_id": "chunk-1",
                "title": "Runbook",
                "text": "Check pod CPU.",
                "source": "k8s",
                "score": 0.9,
            },
        ),
        (
            SafetyResult,
            {
                "command": "kubectl get pods",
                "level": "SAFE",
                "reason": "read only",
            },
        ),
    ]

    for model, payload in samples:
        with pytest.raises(ValidationError):
            model(**(payload | {"unexpected": "value"}))


def test_generate_logs_has_required_volume_and_labels():
    logs = generate_logs(seed=7, per_service=200)
    normal_count = sum(1 for item in logs if not item.is_anomaly)
    anomaly_types = {item.anomaly_type for item in logs if item.is_anomaly}

    assert len(logs) >= 1000
    assert normal_count >= 200
    assert {"latency_spike", "transaction_conflict", "queue_backlog"} <= anomaly_types

    for anomaly_type in anomaly_types:
        assert sum(1 for item in logs if item.anomaly_type == anomaly_type) >= 10


def test_generate_logs_pins_core_contract():
    per_service = 200
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    logs = generate_logs(seed=11, per_service=per_service)
    same_seed_logs = generate_logs(seed=11, per_service=per_service)

    assert SERVICES == EXPECTED_SERVICES
    assert logs == same_seed_logs
    assert Counter(item.service for item in logs) == {
        service: per_service for service in EXPECTED_SERVICES
    }
    assert logs[0].timestamp == base_time
    assert logs[0].timestamp.tzinfo == timezone.utc
    assert logs == sorted(logs, key=lambda item: item.timestamp)

    records_by_service = {
        service: [item for item in logs if item.service == service]
        for service in EXPECTED_SERVICES
    }
    for service_offset, service in enumerate(EXPECTED_SERVICES):
        for index, record in enumerate(records_by_service[service]):
            expected_timestamp = base_time + timedelta(
                seconds=index * len(SERVICES) + service_offset
            )
            assert record.timestamp == expected_timestamp
            expected_anomaly_type = "normal"
            if service in {"api-gateway", "business-service"} and 45 <= index < 60:
                expected_anomaly_type = "latency_spike"
            elif service in {"auth-service", "data-service"} and 95 <= index < 125:
                expected_anomaly_type = "transaction_conflict"
            elif service in {"message-queue", "business-service"} and 150 <= index < 180:
                expected_anomaly_type = "queue_backlog"

            assert record.anomaly_type == expected_anomaly_type
            assert record.is_anomaly is (expected_anomaly_type != "normal")


def test_write_jsonl_round_trips_records(tmp_path):
    logs = generate_logs(seed=3, per_service=40)
    output = tmp_path / "nested" / "logs.jsonl"

    assert not output.parent.exists()
    write_jsonl(logs, output)

    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert output.parent.is_dir()
    assert len(rows) == len(logs)
    assert set(rows[0]) == EXPECTED_JSON_KEYS
    assert rows[0]["timestamp"] == logs[0].timestamp.isoformat()


def test_log_record_serializes_timestamp_and_rejects_string_booleans():
    from aiops_agent.models.schemas import LogRecord

    row = generate_logs(seed=3, per_service=1)[0].to_json_dict()

    assert isinstance(row["timestamp"], str)
    with pytest.raises(ValidationError):
        LogRecord(**(row | {"is_anomaly": "false"}))
