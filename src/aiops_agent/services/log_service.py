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
                if not line.strip():
                    continue

                row = json.loads(line)
                payload = dict(row)
                payload["timestamp"] = datetime.fromisoformat(row["timestamp"])
                payload["is_anomaly"] = _parse_bool(row["is_anomaly"])
                records.append(LogRecord.model_validate(payload))
        return records


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
