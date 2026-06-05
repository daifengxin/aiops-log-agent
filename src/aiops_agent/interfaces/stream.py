from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from aiops_agent.graph.builder import build_diagnosis_graph
from aiops_agent.interfaces.cli import _jsonable
from aiops_agent.services.detection_service import DetectionConfig, DetectionService
from aiops_agent.services.log_service import parse_jsonl_line


async def stream_file(
    path: Path,
    emit_interval: float,
    batch_size: int = 20,
    window_seconds: int = 10,
) -> None:
    """逐行消费 JSONL 日志，并按批次异步输出诊断快照。"""

    records = []
    pending_count = 0
    detection = DetectionService(DetectionConfig(window_seconds=window_seconds))
    graph = build_diagnosis_graph(detection_service=detection)

    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            record = parse_jsonl_line(line)
            if record is None:
                continue
            records.append(record)
            pending_count += 1
            if pending_count >= batch_size:
                _emit_snapshot(graph, records)
                pending_count = 0
                # emit_interval 控制文件回放节奏，用于模拟实时日志到达。
                if emit_interval > 0:
                    await asyncio.sleep(emit_interval)

    if pending_count:
        _emit_snapshot(graph, records)


def _emit_snapshot(graph: Any, records: list[Any]) -> None:
    result = _jsonable(graph.invoke({"records": records}))
    event = _stream_event(records_seen=len(records), result=result)
    print(json.dumps(event, ensure_ascii=False), flush=True)


def run_stream(path: Path, window_seconds: int, emit_interval: float) -> None:
    """同步 CLI 包装，把窗口参数传入检测图。"""

    asyncio.run(
        stream_file(
            path=path,
            emit_interval=emit_interval,
            window_seconds=window_seconds,
        )
    )


def _stream_event(records_seen: int, result: dict[str, Any]) -> dict[str, Any]:
    # 流式输出只带诊断摘要，避免每个批次重复输出不断增长的原始日志列表。
    event: dict[str, Any] = {
        "records_seen": records_seen,
        "alert_decision": result.get("alert_decision"),
    }
    for key in (
        "detected_anomalies",
        "llm_report",
        "safe_commands",
        "review_commands",
        "blocked_commands",
        "errors",
    ):
        if key in result:
            event[key] = result[key]
    return event
