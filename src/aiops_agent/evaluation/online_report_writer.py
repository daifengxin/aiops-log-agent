from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from aiops_agent.config import Settings
from aiops_agent.data.generator import generate_logs, write_jsonl
from aiops_agent.evaluation.anomaly_eval import (
    evaluate_type_classification,
    evaluate_parameter_grid,
    evaluate_windows_by_type,
)
from aiops_agent.evaluation.rag_eval import evaluate_chunking_strategies, rag_test_queries
from aiops_agent.evaluation.safety_eval import evaluate_safety_cases, safety_test_cases
from aiops_agent.models.schemas import LogRecord
from aiops_agent.rag.k8s_loader import load_curated_k8s_docs
from aiops_agent.services.llm_service import GeminiLLMService
from aiops_agent.services.safety_service import CommandSafetyService


class JsonLLMService(Protocol):
    def generate_json(self, prompt: str) -> dict[str, Any]:
        """返回 JSON 对象；真实实现由 GeminiLLMService 提供。"""


def sample_online_eval_records(
    records: list[LogRecord],
    *,
    normal_count: int = 200,
    anomaly_count: int = 40,
) -> list[LogRecord]:
    """抽样在线评估集：200 normal + 20 latency_spike + 20 transaction_conflict。"""

    latency_count = anomaly_count // 2
    transaction_count = anomaly_count - latency_count
    normal_records = [record for record in records if not record.is_anomaly]
    latency_records = [
        record for record in records if record.anomaly_type == "latency_spike"
    ]
    transaction_records = [
        record for record in records if record.anomaly_type == "transaction_conflict"
    ]
    if len(normal_records) < normal_count:
        raise ValueError("not enough normal records for online evaluation")
    if len(latency_records) < latency_count:
        raise ValueError("not enough latency_spike records for online evaluation")
    if len(transaction_records) < transaction_count:
        raise ValueError("not enough transaction_conflict records for online evaluation")

    sample = (
        normal_records[:normal_count]
        + latency_records[:latency_count]
        + transaction_records[:transaction_count]
    )
    return sorted(sample, key=lambda record: record.timestamp)


def write_online_gemini_report(
    settings: Settings,
    llm_service: JsonLLMService | None = None,
) -> None:
    """生成在线评估报告：指标本地计算，量化附录由真实 Gemini 调用生成。"""

    settings.ensure_dirs()
    records = sample_online_eval_records(generate_logs(seed=42, per_service=220))
    write_jsonl(records, settings.eval_dir / "online_sample.jsonl")

    metrics = _evaluate_online_metrics(records)
    service = llm_service or GeminiLLMService(settings)
    prompt = _build_appendix_prompt(metrics)
    gemini_response = service.generate_json(prompt)
    appendix = _extract_appendix(gemini_response)

    artifact = {
        **metrics,
        "gemini_model": settings.gemini_model,
        "gemini_response": gemini_response,
    }
    (settings.eval_dir / "online_gemini_evaluation.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (settings.reports_dir / "gemini_evaluation.md").write_text(
        _render_report(metrics, appendix, settings.gemini_model),
        encoding="utf-8",
    )


def _evaluate_online_metrics(records: list[LogRecord]) -> dict[str, Any]:
    docs = load_curated_k8s_docs()
    queries = rag_test_queries()
    anomaly_grid = evaluate_parameter_grid(
        records,
        alphas=[0.1, 0.2, 0.3],
        thresholds=[2.0, 2.5, 3.0],
        window_seconds=10,
    )
    window_rows = evaluate_windows_by_type(
        records,
        alpha=0.2,
        threshold=2.5,
        windows=[1, 10, 60],
    )
    type_rows = evaluate_type_classification(
        records,
        alpha=0.2,
        threshold=2.5,
        window_seconds=10,
    )
    rag_rows = evaluate_chunking_strategies(docs, queries)
    safety_rows = evaluate_safety_cases(CommandSafetyService(), safety_test_cases())
    return {
        "sample_counts": _sample_counts(records),
        "anomaly_grid": anomaly_grid,
        "window_rows": window_rows,
        "type_rows": type_rows,
        "rag_rows": rag_rows,
        "safety_rows": safety_rows,
        "optimization_comparison": _optimization_comparison(anomaly_grid),
        "rag_query_count": len(queries),
    }


def _build_appendix_prompt(metrics: dict[str, Any]) -> str:
    payload = json.dumps(metrics, ensure_ascii=False, indent=2)
    return (
        "你是 AIOps 评估报告助手。请只返回 JSON，格式为："
        '{"quantitative_appendix_markdown": "..."}。'
        "quantitative_appendix_markdown 必须是中文 Markdown，必须覆盖："
        "1) 3x3 异常检测参数敏感性 Precision/Recall/F1；"
        "2) 1s/10s/60s 在 latency_spike 和 transaction_conflict 上的 F1 对比，"
        "必须明确写出哪种粒度更适合哪类异常以及原因；"
        "3) 严格 anomaly_type 级别 Precision/Recall/F1；"
        "4) 两种 RAG chunking 在 10 条 query 上的 Recall@5，以及哪类 query 更受影响；"
        "5) 命令安全分级准确率和误分类案例；"
        "6) 至少一个优化前 vs 优化后对比。"
        "所有数字只能来自下面 JSON，不允许编造。\n"
        f"metrics_json:\n{payload}"
    )


def _extract_appendix(response: dict[str, Any]) -> str:
    appendix = response.get("quantitative_appendix_markdown")
    if not isinstance(appendix, str) or not appendix.strip():
        raise ValueError("Gemini response missing quantitative_appendix_markdown")
    return appendix.strip()


def _sample_counts(records: list[LogRecord]) -> dict[str, int]:
    type_counts = Counter(record.anomaly_type for record in records if record.is_anomaly)
    return {
        "normal": sum(1 for record in records if not record.is_anomaly),
        "anomaly": sum(1 for record in records if record.is_anomaly),
        "latency_spike": type_counts["latency_spike"],
        "transaction_conflict": type_counts["transaction_conflict"],
    }


def _optimization_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    before = _find_grid_row(rows, alpha=0.3, z_threshold=2.5)
    after = _find_grid_row(rows, alpha=0.1, z_threshold=2.5)
    return {
        "change": "alpha 0.3 -> 0.1 with z_threshold 2.5",
        "before": before,
        "after": after,
        "f1_delta": round(float(after["f1"]) - float(before["f1"]), 4),
    }


def _find_grid_row(
    rows: list[dict[str, Any]],
    *,
    alpha: float,
    z_threshold: float,
) -> dict[str, Any]:
    for row in rows:
        if row["alpha"] == alpha and row["z_threshold"] == z_threshold:
            return row
    raise ValueError(f"missing grid row alpha={alpha}, z_threshold={z_threshold}")


def _render_report(
    metrics: dict[str, Any],
    appendix: str,
    gemini_model: str,
) -> str:
    safety_accuracy = _accuracy(metrics["safety_rows"])
    counts = metrics["sample_counts"]
    return "\n\n".join(
        [
            "# Gemini 在线量化评估报告",
            (
                "## 结论\n\n"
                f"本报告由 `evaluate-online` 生成：先在已标注子集 "
                f"{counts['normal']} normal + {counts['anomaly']} anomaly 上计算量化指标，"
                f"再调用 `{gemini_model}` 生成量化评估附录。"
                "报告中的指标来自本地可复现评估代码，附录文字来自真实 Gemini 在线调用。"
            ),
            (
                "## 在线评估证据\n\n"
                "| 项目 | 值 |\n"
                "|---|---|\n"
                "| CLI | `uv run python -m aiops_agent.interfaces.cli evaluate-online` |\n"
                f"| 模型 | `{gemini_model}` |\n"
                "| 抽样数据 | `data/eval/online_sample.jsonl` |\n"
                "| 证据 JSON | `data/eval/online_gemini_evaluation.json` |\n"
                f"| 命令安全准确率 | {safety_accuracy:.2%} |"
            ),
            "## 抽样数据集\n\n" + _markdown_table([counts]),
            "## 异常检测参数敏感性\n\n" + _markdown_table(metrics["anomaly_grid"]),
            "## 多粒度窗口对比\n\n" + _markdown_table(metrics["window_rows"]),
            "## 异常类型识别准确性\n\n" + _markdown_table(metrics["type_rows"]),
            "## RAG 检索质量\n\n" + _markdown_table(metrics["rag_rows"]),
            "## 命令安全分级准确性\n\n" + _markdown_table(metrics["safety_rows"]),
            (
                "## 优化前 vs 优化后\n\n"
                + _markdown_table([metrics["optimization_comparison"]])
            ),
            appendix,
            "",
        ]
    )


def _accuracy(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["expected"] == row["predicted"]) / len(rows)


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(key)) for key in headers) + " |")
    return "\n".join(lines)


def _format_cell(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    # Markdown 表格中管道符会拆列，必须转义命令里的 shell pipe。
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
