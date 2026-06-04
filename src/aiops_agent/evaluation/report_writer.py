from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from aiops_agent.config import Settings
from aiops_agent.data.generator import generate_logs
from aiops_agent.evaluation.anomaly_eval import (
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
from aiops_agent.services.safety_service import CommandSafetyService

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def write_full_report(settings: Settings) -> None:
    """生成离线评估报告和配套图表，不触发 Gemini 或网络调用。"""

    settings.ensure_dirs()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.figures_dir.mkdir(parents=True, exist_ok=True)

    records = generate_logs(seed=42, per_service=220)
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
    rag_rows = evaluate_chunking_strategies(
        load_curated_k8s_docs(),
        rag_test_queries(),
    )
    safety_rows = evaluate_safety_cases(
        CommandSafetyService(),
        safety_test_cases(),
    )

    figure_paths = _write_figures(
        figures_dir=settings.figures_dir,
        anomaly_grid=anomaly_grid,
        window_rows=window_rows,
        rag_rows=rag_rows,
    )
    report = _render_report(
        anomaly_grid=anomaly_grid,
        window_rows=window_rows,
        rag_rows=rag_rows,
        safety_rows=safety_rows,
        figure_paths=figure_paths,
    )
    (settings.reports_dir / "evaluation.md").write_text(report, encoding="utf-8")


def _render_report(
    anomaly_grid: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    rag_rows: list[dict[str, Any]],
    safety_rows: list[dict[str, Any]],
    figure_paths: dict[str, Path],
) -> str:
    safety_accuracy = _accuracy(safety_rows)
    best_grid = max(anomaly_grid, key=lambda row: float(row["f1"]))
    best_rag = max(rag_rows, key=lambda row: float(row["recall_at_5"]))

    sections = [
        "# AIOps Log Agent 离线评估报告",
        (
            "## 异常检测参数敏感性\n\n"
            "固定 10 秒窗口，对 alpha 与 z_threshold 做网格评估；F1 越高表示窗口级"
            "异常检测越稳健。\n\n"
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
            + _markdown_table(safety_rows)
        ),
        (
            "## 告警抑制策略\n\n"
            "建议以 service、window_seconds、bucket_start 和 anomaly_type 作为去重键，"
            "在短时间内只保留同一根因的最高严重度告警。这样可以压缩延迟尖刺期间的重复"
            "窗口告警，同时保留跨服务或跨异常类型的排障线索。"
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
) -> dict[str, Path]:
    paths = {
        "threshold_f1": figures_dir / "anomaly_threshold_f1.png",
        "window_f1": figures_dir / "anomaly_window_f1.png",
        "rag_recall": figures_dir / "rag_recall_at_5.png",
    }
    _plot_threshold_f1(anomaly_grid, paths["threshold_f1"])
    _plot_window_f1(window_rows, paths["window_f1"])
    _plot_rag_recall(rag_rows, paths["rag_recall"])
    return paths


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
