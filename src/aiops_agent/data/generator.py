from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiops_agent.data.schemas import LogRecord

SERVICES = [
    "api-gateway",
    "auth-service",
    "business-service",
    "data-service",
    "message-queue",
]
ENDPOINTS = ["/login", "/orders", "/checkout", "/profile", "/events"]

_BASE_LATENCY_MS = {
    "api-gateway": 95.0,
    "auth-service": 70.0,
    "business-service": 130.0,
    "data-service": 115.0,
    "message-queue": 45.0,
}
_BASE_CPU_PCT = {
    "api-gateway": 38.0,
    "auth-service": 32.0,
    "business-service": 46.0,
    "data-service": 43.0,
    "message-queue": 28.0,
}
_BASE_MEMORY_MB = {
    "api-gateway": 640.0,
    "auth-service": 520.0,
    "business-service": 860.0,
    "data-service": 1024.0,
    "message-queue": 420.0,
}
_DEPENDENCIES = {
    "api-gateway": "auth-service",
    "auth-service": "data-service",
    "business-service": "data-service",
    "data-service": "postgres",
    "message-queue": "business-service",
}


def generate_logs(seed: int = 42, per_service: int = 220) -> list[LogRecord]:
    rng = random.Random(seed)
    base_time = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    records: list[LogRecord] = []

    for service_offset, service in enumerate(SERVICES):
        for index in range(per_service):
            anomaly_type = _anomaly_type(service, index)
            error_code, status_code = _error(service, anomaly_type, rng)
            timestamp = base_time + timedelta(
                seconds=index * len(SERVICES) + service_offset
            )
            records.append(
                LogRecord(
                    timestamp=timestamp,
                    service=service,
                    latency_ms=_latency(service, anomaly_type, rng),
                    error_code=error_code,
                    request_id=_request_id(service, index, rng),
                    endpoint=ENDPOINTS[(index + service_offset) % len(ENDPOINTS)],
                    status_code=status_code,
                    cpu_pct=_cpu(service, anomaly_type, rng),
                    memory_mb=_memory(service, anomaly_type, rng),
                    queue_depth=_queue_depth(service, anomaly_type, rng),
                    dependency=_dependency(service, anomaly_type),
                    anomaly_type=anomaly_type,
                    is_anomaly=anomaly_type != "normal",
                )
            )

    return sorted(records, key=lambda item: item.timestamp)


def write_jsonl(records: list[LogRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record.to_json_dict(), ensure_ascii=False) + "\n")


def _anomaly_type(service: str, index: int) -> str:
    # 这里固定异常注入窗口，保证后续评测能用 seed 复现实验标签。
    if service in {"api-gateway", "business-service"} and 45 <= index < 60:
        return "latency_spike"
    if service in {"auth-service", "data-service"} and 95 <= index < 125:
        return "transaction_conflict"
    if service in {"message-queue", "business-service"} and 150 <= index < 180:
        return "queue_backlog"
    return "normal"


def _latency(service: str, anomaly_type: str, rng: random.Random) -> float:
    base = _BASE_LATENCY_MS[service]
    jitter = rng.gauss(0, base * 0.08)
    multiplier = {
        "latency_spike": 4.2,
        "transaction_conflict": 1.6,
        "queue_backlog": 2.3,
        "normal": 1.0,
    }[anomaly_type]
    return round(max(1.0, (base + jitter) * multiplier), 2)


def _error(
    service: str,
    anomaly_type: str,
    rng: random.Random,
) -> tuple[str, int]:
    if anomaly_type == "transaction_conflict":
        return "TX_CONFLICT", 409
    if anomaly_type == "latency_spike" and rng.random() < 0.35:
        return "UPSTREAM_TIMEOUT", 504
    if anomaly_type == "queue_backlog" and rng.random() < 0.25:
        return "QUEUE_BACKLOG", 503
    if service == "api-gateway" and rng.random() < 0.02:
        return "BAD_GATEWAY", 502
    return "NONE", 200


def _queue_depth(service: str, anomaly_type: str, rng: random.Random) -> int:
    if anomaly_type == "queue_backlog":
        return int(rng.uniform(350, 750))
    base = 45 if service == "message-queue" else 18
    return max(0, int(rng.gauss(base, 8)))


def _dependency(service: str, anomaly_type: str) -> str:
    if anomaly_type == "latency_spike":
        return _DEPENDENCIES[service]
    if anomaly_type == "transaction_conflict":
        return "postgres"
    if anomaly_type == "queue_backlog":
        return "kafka"
    return _DEPENDENCIES[service]


def _cpu(service: str, anomaly_type: str, rng: random.Random) -> float:
    bump = 24.0 if anomaly_type in {"latency_spike", "transaction_conflict"} else 0.0
    if anomaly_type == "queue_backlog":
        bump = 16.0
    return round(min(99.0, max(1.0, rng.gauss(_BASE_CPU_PCT[service] + bump, 6))), 2)


def _memory(service: str, anomaly_type: str, rng: random.Random) -> float:
    bump = 160.0 if anomaly_type == "queue_backlog" else 0.0
    if anomaly_type == "transaction_conflict":
        bump = 96.0
    return round(max(64.0, rng.gauss(_BASE_MEMORY_MB[service] + bump, 48)), 2)


def _request_id(service: str, index: int, rng: random.Random) -> str:
    service_key = service.replace("-", "")
    return f"req-{service_key}-{index:05d}-{rng.randrange(10_000):04d}"
