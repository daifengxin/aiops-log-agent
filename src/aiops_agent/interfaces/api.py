from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from aiops_agent.graph.builder import build_diagnosis_graph
from aiops_agent.interfaces.cli import _jsonable
from aiops_agent.services.log_service import LogService


class DiagnoseRequest(BaseModel):
    """HTTP 诊断请求体；接口层本地模型，不进入核心 DTO。"""

    log_file: str
    limit: int = 80


app = FastAPI(title="AIOps Log Agent")
_diagnosis_graph: Any | None = None


def _get_graph() -> Any:
    """API 进程内复用同一个 graph，保留 AlertService 的短时抑制状态。"""

    global _diagnosis_graph
    if _diagnosis_graph is None:
        _diagnosis_graph = build_diagnosis_graph()
    return _diagnosis_graph


@app.post("/diagnose")
def diagnose(request: DiagnoseRequest) -> dict[str, Any]:
    """读取 JSONL 日志并返回诊断图结果，保留 review_commands 等分级字段。"""

    records = LogService().read_jsonl(Path(request.log_file), request.limit)
    result = _get_graph().invoke({"records": records})
    return _jsonable(result)
