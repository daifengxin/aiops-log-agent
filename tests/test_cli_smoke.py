import json
from datetime import datetime, timezone
from pathlib import Path

from aiops_agent.interfaces.cli import _jsonable, main
from aiops_agent.models.schemas import DetectedAnomaly, SafetyResult


def test_generate_data_command_creates_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["generate-data", "--seed", "5", "--per-service", "40"])

    assert exit_code == 0
    assert (tmp_path / "data" / "logs" / "test_logs.jsonl").is_file()


def test_evaluate_safety_command_prints_accuracy(capsys):
    exit_code = main(["evaluate-safety"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "accuracy" in output


def test_jsonable_preserves_command_buckets_and_serializes_runtime_types():
    timestamp = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)
    result = {
        "detected_anomalies": [
            DetectedAnomaly(
                service="api-gateway",
                window_seconds=10,
                bucket_start=timestamp,
                score=3.2,
                metric_name="latency_p95",
                anomaly_type="latency_spike",
                reason="latency p95 exceeded baseline",
            )
        ],
        "safe_commands": [
            SafetyResult(command="kubectl get pods", level="SAFE", reason="read only")
        ],
        "review_commands": [
            SafetyResult(
                command="kubectl rollout restart deployment/api",
                level="CAUTION",
                reason="needs review",
            )
        ],
        "blocked_commands": [
            SafetyResult(
                command="kubectl delete pod api-0",
                level="DANGER",
                reason="destructive",
            )
        ],
        "report_path": Path("reports/evaluation.md"),
    }

    payload = _jsonable(result)
    encoded = json.dumps(payload)

    assert "review_commands" in encoded
    assert payload["detected_anomalies"][0]["bucket_start"] == "2026-06-05T09:00:00Z"
    assert payload["review_commands"][0]["level"] == "CAUTION"
    assert payload["blocked_commands"][0]["level"] == "DANGER"
    assert payload["report_path"] == "reports/evaluation.md"
