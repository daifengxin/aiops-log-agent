from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from aiops_agent.graph.builder import build_diagnosis_graph
from aiops_agent.interfaces.cli import _jsonable
from aiops_agent.services.detection_service import DetectionConfig, DetectionService
from aiops_agent.services.log_service import LogService


async def stream_file(
    path: Path,
    emit_interval: float,
    batch_size: int = 20,
    window_seconds: int = 10,
) -> None:
    """一次性读取日志，然后按增长窗口异步输出诊断快照。"""

    records = LogService().read_jsonl(path)
    detection = DetectionService(DetectionConfig(window_seconds=window_seconds))
    graph = build_diagnosis_graph(detection_service=detection)
    for end in range(batch_size, len(records) + batch_size, batch_size):
        batch = records[: min(end, len(records))]
        if not batch:
            break

        result = _jsonable(graph.invoke({"records": batch}))
        event = _stream_event(records_seen=len(batch), result=result)
        print(json.dumps(event, ensure_ascii=False), flush=True)

        if len(batch) < len(records):
            await asyncio.sleep(emit_interval)


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
