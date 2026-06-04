from aiops_agent.data.generator import generate_logs
from aiops_agent.detection.ewma import ewma
from aiops_agent.detection.zscore import z_scores
from aiops_agent.detection.windows import aggregate_windows
from aiops_agent.services.detection_service import DetectionConfig, DetectionService


def test_ewma_responds_to_recent_values():
    values = [10.0, 10.0, 10.0, 100.0]
    slow = ewma(values, alpha=0.1)
    fast = ewma(values, alpha=0.3)

    assert fast[-1] > slow[-1]


def test_z_scores_flags_spike():
    scores = z_scores([10.0, 11.0, 9.0, 10.5, 80.0])
    assert scores[-1] > 2.0


def test_aggregate_windows_preserves_anomaly_labels():
    records = generate_logs(seed=5, per_service=80)
    windows = aggregate_windows(records, window_seconds=10)
    assert any(window.is_anomaly for window in windows)
    assert any("latency_spike" in window.anomaly_types for window in windows)


def test_detection_service_finds_known_anomalies():
    records = generate_logs(seed=11, per_service=220)
    service = DetectionService(DetectionConfig(alpha=0.2, z_threshold=2.0, window_seconds=10))
    anomalies = service.detect(records)

    assert anomalies
    assert {item.anomaly_type for item in anomalies} & {"latency_spike", "transaction_conflict", "queue_backlog"}
