from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from aiops_agent.config import Settings
from aiops_agent.data.generator import generate_logs, write_jsonl
from aiops_agent.evaluation.safety_eval import (
    evaluate_safety_cases,
    safety_test_cases,
)
from aiops_agent.services.log_service import LogService
from aiops_agent.services.safety_service import CommandSafetyService


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器，所有子命令只编排已有服务。"""

    parser = argparse.ArgumentParser(prog="aiops-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-data")
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--per-service", type=int, default=220)
    generate.set_defaults(handler=_handle_generate_data)

    diagnose = subparsers.add_parser("diagnose")
    diagnose.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data/logs/test_logs.jsonl"),
    )
    diagnose.add_argument("--limit", type=int, default=80)
    diagnose.set_defaults(handler=_handle_diagnose)

    evaluate_safety = subparsers.add_parser("evaluate-safety")
    evaluate_safety.set_defaults(handler=_handle_evaluate_safety)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.set_defaults(handler=_handle_evaluate)

    build_rag = subparsers.add_parser("build-rag")
    build_rag.set_defaults(handler=_handle_build_rag)

    stream = subparsers.add_parser("stream")
    stream.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data/logs/test_logs.jsonl"),
    )
    stream.add_argument(
        "--window",
        "--window-seconds",
        dest="window_seconds",
        type=int,
        default=10,
    )
    stream.add_argument("--emit-interval", type=float, default=1.0)
    stream.set_defaults(handler=_handle_stream)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        args.handler(args)
        return 0
    except SystemExit as exc:
        return int(exc.code)
    except Exception as exc:  # pragma: no cover - smoke tests覆盖成功路径
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _jsonable(value: Any) -> Any:
    """把接口返回值递归转换为 JSON 原生类型，不筛掉图状态中的命令分级列表。"""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _handle_generate_data(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    settings.ensure_dirs()
    output_path = settings.logs_dir / "test_logs.jsonl"
    records = generate_logs(seed=args.seed, per_service=args.per_service)
    write_jsonl(records, output_path)
    print(output_path)


def _handle_evaluate_safety(args: argparse.Namespace) -> None:
    del args
    cases = evaluate_safety_cases(CommandSafetyService(), safety_test_cases())
    payload = {"accuracy": _accuracy(cases), "cases": cases}
    _print_json(payload)


def _handle_diagnose(args: argparse.Namespace) -> None:
    from aiops_agent.graph.builder import build_diagnosis_graph

    records = LogService().read_jsonl(args.path, args.limit)
    result = build_diagnosis_graph().invoke({"records": records})
    _print_json(result)


def _handle_evaluate(args: argparse.Namespace) -> None:
    from aiops_agent.evaluation.report_writer import write_full_report

    del args
    settings = Settings.from_env()
    write_full_report(settings)
    print(settings.reports_dir / "evaluation.md")


def _handle_build_rag(args: argparse.Namespace) -> None:
    del args
    print("Curated offline Kubernetes corpus is available; RAG index is lazy-built during diagnosis.")


def _handle_stream(args: argparse.Namespace) -> None:
    # 延迟导入避免仅查看 CLI help 或跑 safety eval 时加载流式诊断依赖。
    from aiops_agent.interfaces.stream import run_stream

    run_stream(
        path=args.path,
        window_seconds=args.window_seconds,
        emit_interval=args.emit_interval,
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2))


def _accuracy(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    matches = sum(1 for row in rows if row["expected"] == row["predicted"])
    return matches / len(rows)


if __name__ == "__main__":
    raise SystemExit(main())
