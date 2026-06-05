from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aiops_agent.models.schemas import LogRecord


class LogService:
    def read_jsonl(self, path: Path, limit: int | None = None) -> list[LogRecord]:
        records: list[LogRecord] = []
        with path.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                if limit is not None and len(records) >= limit:
                    break
                record = parse_jsonl_line(line)
                if record is None:
                    continue
                records.append(record)
        return records


def parse_jsonl_line(line: str) -> LogRecord | None:
    """解析单条 JSONL 日志；流式入口复用它，避免一次性读完整文件。"""

    if not line.strip():
        return None
    row = json.loads(line)
    payload = dict(row)
    payload["timestamp"] = datetime.fromisoformat(row["timestamp"])
    payload["is_anomaly"] = _parse_bool(row["is_anomaly"])
    return LogRecord.model_validate(payload)


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False

    raise ValueError(f"is_anomaly must be a boolean value, got {value!r}")
