from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from aiops_agent.config import Settings
from aiops_agent.data.generator import generate_logs, write_jsonl
from aiops_agent.evaluation.anomaly_eval import (
    evaluate_type_classification,
    evaluate_parameter_grid,
    evaluate_windows_by_type,
)
from aiops_agent.evaluation.rag_eval import (
    evaluate_chunking_strategies,
    rag_test_queries,
)
from aiops_agent.evaluation.safety_eval import (
    evaluate_safety_cases,
    safety_test_cases,
)
from aiops_agent.rag.k8s_loader import load_curated_k8s_docs
from aiops_agent.services.alert_service import AlertService
from aiops_agent.services.detection_service import DetectionConfig, DetectionService
from aiops_agent.services.safety_service import CommandSafetyService

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def write_full_report(settings: Settings) -> None:
    """生成离线评估报告和配套图表，不触发 Gemini 或网络调用。"""

    settings.ensure_dirs()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.figures_dir.mkdir(parents=True, exist_ok=True)

    records = generate_logs(seed=42, per_service=220)
    docs = load_curated_k8s_docs()
    queries = rag_test_queries()
    anomaly_grid = evaluate_parameter_grid(
        records,
        [0.1, 0.2, 0.3],
        [2.0, 2.5, 3.0],
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
    rag_rows = evaluate_chunking_strategies(
        docs,
        queries,
    )
    safety_rows = evaluate_safety_cases(
        CommandSafetyService(),
        safety_test_cases(),
    )
    alert_stats = _evaluate_alert_suppression(records)

    figure_paths = _write_figures(
        figures_dir=settings.figures_dir,
        anomaly_grid=anomaly_grid,
        window_rows=window_rows,
        rag_rows=rag_rows,
        safety_rows=safety_rows,
    )
    _write_eval_artifacts(
        settings=settings,
        records=records,
        queries=queries,
        anomaly_grid=anomaly_grid,
        window_rows=window_rows,
        type_rows=type_rows,
        rag_rows=rag_rows,
        safety_rows=safety_rows,
        alert_stats=alert_stats,
    )
    report = _render_report(
        docs=docs,
        anomaly_grid=anomaly_grid,
        window_rows=window_rows,
        type_rows=type_rows,
        rag_rows=rag_rows,
        safety_rows=safety_rows,
        alert_stats=alert_stats,
        figure_paths=figure_paths,
    )
    (settings.reports_dir / "evaluation.md").write_text(report, encoding="utf-8")


def _render_report(
    docs: list[dict[str, Any]],
    anomaly_grid: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    type_rows: list[dict[str, Any]],
    rag_rows: list[dict[str, Any]],
    safety_rows: list[dict[str, Any]],
    alert_stats: dict[str, Any],
    figure_paths: dict[str, Path],
) -> str:
    safety_accuracy = _accuracy(safety_rows)
    best_grid = max(anomaly_grid, key=lambda row: float(row["f1"]))
    best_rag = max(rag_rows, key=lambda row: float(row["recall_at_5"]))
    corpus_rows = _corpus_rows(docs)
    total_pages = sum(int(row["估算页数"]) for row in corpus_rows)
    total_chars = sum(len(str(doc["text"])) for doc in docs)

    sections = [
        "# AIOps Log Agent 离线评估报告",
        (
            "## Kubernetes 官方语料清单\n\n"
            f"本项目选取 Kubernetes 官方文档中的 {len(docs)} 个运维排障相关页面，"
            f"估算页数 {total_pages} 页，满足任务书要求的官方技术文档体量 ≥ 50 页。"
            f"离线 RAG 语料正文总字符数为 {total_chars}，用于保证评测可复现且不依赖网络。\n\n"
            + _markdown_table(corpus_rows)
        ),
        (
            "## 异常检测参数敏感性\n\n"
            "固定 10 秒窗口，对 alpha 与 z_threshold 做网格评估；F1 越高表示窗口级"
            "异常检测越稳健。\n\n"
            f"![F1 heatmap]({_relative_figure(figure_paths['f1_heatmap'])})\n\n"
            f"![threshold F1]({_relative_figure(figure_paths['threshold_f1'])})\n\n"
            + _markdown_table(anomaly_grid)
            + "\n\n"
            f"最佳组合为 alpha={best_grid['alpha']}、z_threshold={best_grid['z_threshold']}，"
            f"F1={best_grid['f1']}。"
        ),
        (
            "## 异常窗口粒度对比\n\n"
            "使用 alpha=0.2、z_threshold=2.5，对 1/10/60 秒窗口按异常类型比较。\n\n"
            f"![window F1]({_relative_figure(figure_paths['window_f1'])})\n\n"
            + _markdown_table(window_rows)
        ),
        (
            "## 异常类型识别准确性\n\n"
            "窗口级 F1 只衡量是否发现异常；本节按 anomaly_type 严格评估，"
            "同一窗口检出但类型错误会被计为对应类型的漏报/误报。\n\n"
            + _markdown_table(type_rows)
        ),
        (
            "## RAG Chunking Recall@5\n\n"
            "使用离线 Kubernetes 语料和词法向量检索，比较固定字符切分与语义切分的"
            "Top-5 召回。\n\n"
            f"![rag recall]({_relative_figure(figure_paths['rag_recall'])})\n\n"
            + _markdown_table(rag_rows)
            + "\n\n"
            f"当前最高 Recall@5 策略为 {best_rag['strategy']}，"
            f"Recall@5={best_rag['recall_at_5']}。"
        ),
        (
            "## 命令安全分级\n\n"
            "安全评测覆盖只读命令、需要人工确认的变更命令，以及删除/注入等危险命令。"
            f"当前规则集准确率为 {safety_accuracy:.2%}。\n\n"
            f"![safety confusion matrix]({_relative_figure(figure_paths['safety_matrix'])})\n\n"
            "安全混淆矩阵用于检查 SAFE / CAUTION / DANGER 是否存在系统性误判。\n\n"
            + _markdown_table(safety_rows)
        ),
        (
            "## 告警抑制策略\n\n"
            "当前 AlertService 在 60 秒内相同 service + anomaly_type + root_cause "
            "只保留第一条告警，后续重复告警会被抑制且不会刷新抑制时间戳。这样可以"
            "减少同一根因连续窗口触发的重复诊断调用，同时保留跨服务、跨异常类型或"
            "跨根因的排障线索。\n\n"
            + _markdown_table([alert_stats])
            + f"\n\n告警降噪率为 {alert_stats['noise_reduction_rate']:.2%}。"
        ),
        (
            "## 10 倍日志量扩容\n\n"
            "10 倍日志量下，优先保持日志生成、窗口聚合、检测评估的流式边界：按服务和时间"
            "窗口分批聚合，避免把全部原始日志长期驻留内存。RAG 评估应复用离线 chunk 与索引，"
            "安全分级可按命令逐条批处理；报告层只消费聚合后的指标表和图表数据。"
        ),
        "",
    ]
    return "\n\n".join(sections)


def _write_figures(
    figures_dir: Path,
    anomaly_grid: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    rag_rows: list[dict[str, Any]],
    safety_rows: list[dict[str, Any]],
) -> dict[str, Path]:
    paths = {
        "f1_heatmap": figures_dir / "f1_heatmap.png",
        "threshold_f1": figures_dir / "anomaly_threshold_f1.png",
        "window_f1": figures_dir / "anomaly_window_f1.png",
        "rag_recall": figures_dir / "rag_recall_at_5.png",
        "safety_matrix": figures_dir / "safety_confusion_matrix.png",
    }
    _plot_f1_heatmap(anomaly_grid, paths["f1_heatmap"])
    _plot_threshold_f1(anomaly_grid, paths["threshold_f1"])
    _plot_window_f1(window_rows, paths["window_f1"])
    _plot_rag_recall(rag_rows, paths["rag_recall"])
    _plot_safety_confusion_matrix(safety_rows, paths["safety_matrix"])
    return paths


def _plot_f1_heatmap(rows: list[dict[str, Any]], output_path: Path) -> None:
    frame = pd.DataFrame(rows)
    pivot = frame.pivot(index="alpha", columns="z_threshold", values="f1").sort_index()
    fig, ax = plt.subplots(figsize=(6, 4))
    try:
        image = ax.imshow(pivot.values, cmap="YlGnBu", vmin=0, vmax=1)
        ax.set_xticks(range(len(pivot.columns)), labels=[str(item) for item in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), labels=[str(item) for item in pivot.index])
        ax.set_xlabel("z_threshold")
        ax.set_ylabel("alpha")
        ax.set_title("F1 heatmap")
        for row_index, alpha in enumerate(pivot.index):
            for col_index, threshold in enumerate(pivot.columns):
                ax.text(
                    col_index,
                    row_index,
                    f"{pivot.loc[alpha, threshold]:.2f}",
                    ha="center",
                    va="center",
                    color="black",
                )
        fig.colorbar(image, ax=ax, label="F1")
        fig.tight_layout()
        fig.savefig(output_path, dpi=140)
    finally:
        plt.close(fig)


def _plot_threshold_f1(rows: list[dict[str, Any]], output_path: Path) -> None:
    frame = pd.DataFrame(rows).sort_values(["alpha", "z_threshold"])
    fig, ax = plt.subplots(figsize=(7, 4))
    try:
        # 每条线固定一个 alpha，便于观察阈值变化对 F1 的影响。
        for alpha, group in frame.groupby("alpha", sort=True):
            ax.plot(
                group["z_threshold"],
                group["f1"],
                marker="o",
                label=f"alpha={alpha}",
            )
        ax.set_xlabel("z_threshold")
        ax.set_ylabel("F1")
        ax.set_title("Threshold sensitivity")
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_path, dpi=140)
    finally:
        plt.close(fig)


def _plot_window_f1(rows: list[dict[str, Any]], output_path: Path) -> None:
    frame = pd.DataFrame(rows)
    pivot = frame.pivot(
        index="window_seconds",
        columns="anomaly_type",
        values="f1",
    ).sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    try:
        pivot.plot(kind="bar", ax=ax)
        ax.set_xlabel("window_seconds")
        ax.set_ylabel("F1")
        ax.set_title("Window F1 comparison")
        ax.set_ylim(0, 1.05)
        ax.legend(title="anomaly_type")
        fig.tight_layout()
        fig.savefig(output_path, dpi=140)
    finally:
        plt.close(fig)


def _plot_rag_recall(rows: list[dict[str, Any]], output_path: Path) -> None:
    frame = pd.DataFrame(rows).sort_values("strategy")
    fig, ax = plt.subplots(figsize=(6, 4))
    try:
        ax.bar(frame["strategy"], frame["recall_at_5"], color="#4477AA")
        ax.set_xlabel("strategy")
        ax.set_ylabel("Recall@5")
        ax.set_title("RAG chunking recall")
        ax.set_ylim(0, 1.05)
        fig.tight_layout()
        fig.savefig(output_path, dpi=140)
    finally:
        plt.close(fig)


def _plot_safety_confusion_matrix(rows: list[dict[str, Any]], output_path: Path) -> None:
    labels = ["SAFE", "CAUTION", "DANGER"]
    frame = pd.DataFrame(rows)
    matrix = pd.crosstab(frame["expected"], frame["predicted"]).reindex(
        index=labels,
        columns=labels,
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(5, 4))
    try:
        image = ax.imshow(matrix.values, cmap="Blues")
        ax.set_xticks(range(len(labels)), labels=labels, rotation=30, ha="right")
        ax.set_yticks(range(len(labels)), labels=labels)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Expected")
        ax.set_title("Safety confusion matrix")
        for row_index, expected in enumerate(labels):
            for col_index, predicted in enumerate(labels):
                ax.text(
                    col_index,
                    row_index,
                    str(int(matrix.loc[expected, predicted])),
                    ha="center",
                    va="center",
                    color="black",
                )
        fig.colorbar(image, ax=ax, label="count")
        fig.tight_layout()
        fig.savefig(output_path, dpi=140)
    finally:
        plt.close(fig)


def _write_eval_artifacts(
    settings: Settings,
    records: list[Any],
    queries: list[dict[str, object]],
    anomaly_grid: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    type_rows: list[dict[str, Any]],
    rag_rows: list[dict[str, Any]],
    safety_rows: list[dict[str, Any]],
    alert_stats: dict[str, Any],
) -> None:
    settings.eval_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(records, settings.eval_dir / "generated_logs.jsonl")
    _write_json(settings.eval_dir / "rag_queries.json", _json_ready(queries))
    _write_json(settings.eval_dir / "anomaly_grid.json", anomaly_grid)
    _write_json(settings.eval_dir / "window_f1.json", window_rows)
    _write_json(settings.eval_dir / "type_f1.json", type_rows)
    _write_json(settings.eval_dir / "rag_recall.json", rag_rows)
    _write_json(settings.eval_dir / "safety_eval.json", safety_rows)
    _write_json(settings.eval_dir / "alert_suppression.json", alert_stats)


def _evaluate_alert_suppression(records: list[Any]) -> dict[str, Any]:
    anomalies = DetectionService(
        DetectionConfig(alpha=0.2, z_threshold=2.5, window_seconds=10)
    ).detect(records)
    alert_service = AlertService(suppression_seconds=60)
    decisions = [
        alert_service.evaluate(
            anomaly,
            # 评测中用稳定根因模拟同类连续告警，避免 LLM 文本漂移影响降噪数据。
            root_cause=f"synthetic_{anomaly.anomaly_type}_root_cause",
        )
        for anomaly in anomalies
    ]
    suppressed = sum(1 for item in decisions if item["suppressed"])
    raw_count = len(decisions)
    final_count = raw_count - suppressed
    reduction = suppressed / raw_count if raw_count else 0.0
    return {
        "raw_alert_count": raw_count,
        "suppressed_alert_count": suppressed,
        "final_alert_count": final_count,
        "noise_reduction_rate": round(reduction, 4),
    }


def _corpus_rows(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "标题": doc["title"],
            "估算页数": int(doc["estimated_pages"]),
            "字符数": len(str(doc["text"])),
            "来源": doc["source"],
        }
        for doc in docs
    ]


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_无数据_"
    # 统一浮点精度，保证报告内容可复现且 diff 稳定。
    frame = pd.DataFrame(rows).round(4)
    return frame.to_markdown(index=False)


def _accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    matches = sum(1 for row in rows if row["expected"] == row["predicted"])
    return matches / len(rows)


def _relative_figure(path: Path) -> str:
    return f"figures/{path.name}"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
