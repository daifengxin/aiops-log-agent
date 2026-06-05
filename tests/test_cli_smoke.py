import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from aiops_agent.interfaces.cli import _jsonable, build_parser, main
from aiops_agent.data.generator import generate_logs, write_jsonl
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


def test_stream_parser_accepts_documented_window_option():
    parser = build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if "stream" in (getattr(action, "choices", None) or {})
    )
    stream_parser = subparsers.choices["stream"]
    option_strings = {
        option
        for action in stream_parser._actions
        for option in action.option_strings
    }

    assert "--window" in option_strings

    args = parser.parse_args(["stream", "--window", "10"])
    assert args.window_seconds == 10


def test_evaluate_parser_accepts_all_flag_without_running_report():
    args = build_parser().parse_args(["evaluate", "--all"])

    assert args.all is True


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


def test_api_reuses_compiled_graph_between_requests(monkeypatch):
    import aiops_agent.interfaces.api as api

    calls = 0
    fake_graph = object()

    def fake_build_graph():
        nonlocal calls
        calls += 1
        return fake_graph

    monkeypatch.setattr(api, "_diagnosis_graph", None, raising=False)
    monkeypatch.setattr(api, "build_diagnosis_graph", fake_build_graph)

    assert api._get_graph() is fake_graph
    assert api._get_graph() is fake_graph
    assert calls == 1


def test_stream_file_builds_graph_with_window_seconds(monkeypatch, tmp_path, capsys):
    from aiops_agent.interfaces import stream

    captured: dict[str, int] = {}
    log_path = tmp_path / "logs.jsonl"
    write_jsonl(generate_logs(seed=11, per_service=4)[:20], log_path)

    class FakeGraph:
        def invoke(self, state):
            return {"alert_decision": {"suppressed": False}}

    def fake_build_graph(*, detection_service=None):
        captured["window_seconds"] = detection_service.config.window_seconds
        return FakeGraph()

    monkeypatch.setattr(stream, "build_diagnosis_graph", fake_build_graph)

    asyncio.run(
        stream.stream_file(
            log_path,
            emit_interval=0,
            batch_size=20,
            window_seconds=60,
        )
    )

    assert captured["window_seconds"] == 60
    assert json.loads(capsys.readouterr().out)["records_seen"] == 20


def test_stream_file_reads_jsonl_incrementally_without_full_file_read(monkeypatch, tmp_path, capsys):
    from aiops_agent.interfaces import stream
    from aiops_agent.services.log_service import LogService

    log_path = tmp_path / "logs.jsonl"
    write_jsonl(generate_logs(seed=12, per_service=2)[:6], log_path)

    class FakeGraph:
        def invoke(self, state):
            return {"alert_decision": {"suppressed": False}}

    def fail_read_jsonl(self, path, limit=None):
        raise AssertionError("stream_file should not read the whole file at startup")

    monkeypatch.setattr(LogService, "read_jsonl", fail_read_jsonl)
    monkeypatch.setattr(stream, "build_diagnosis_graph", lambda **kwargs: FakeGraph())

    asyncio.run(
        stream.stream_file(
            log_path,
            emit_interval=0,
            batch_size=3,
            window_seconds=10,
        )
    )

    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["records_seen"] for event in events] == [3, 6]
