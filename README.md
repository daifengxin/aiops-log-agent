# AI Ops Log Agent

评测优先的 AI 运维日志异常检测 Agent，覆盖 EWMA/Z-Score 参数标定、Kubernetes RAG、Gemini 诊断、命令安全分级、告警抑制和 asyncio 流式检测。

## Setup

```bash
uv sync
cp .env.example .env
```

将 Gemini key 写入未提交的 `.env`：

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash
```

## Commands

```bash
uv run python -m aiops_agent.interfaces.cli generate-data
uv run python -m aiops_agent.interfaces.cli build-rag
uv run python -m aiops_agent.interfaces.cli evaluate --all
uv run python -m aiops_agent.interfaces.cli evaluate-safety
uv run python -m aiops_agent.interfaces.cli diagnose data/logs/test_logs.jsonl --limit 80
uv run python -m aiops_agent.interfaces.cli stream data/logs/test_logs.jsonl --window 10 --emit-interval 1
uv run uvicorn aiops_agent.interfaces.api:app --reload
```

`diagnose`、`stream` 和 `/diagnose` 会调用真实 Gemini，需要 `.env` 中存在 `GEMINI_API_KEY`。`build-rag` 使用离线 Kubernetes 语料，真实索引在诊断时按需懒加载。

## Architecture

LangGraph 编排流程：检测 -> RAG -> Gemini -> 命令安全分级 -> 告警抑制。业务逻辑位于 `services/`，统计检测位于 `detection/`，RAG 位于 `rag/`，评测位于 `evaluation/`，接口层位于 `interfaces/`。

命令分级输出分为三类：

- `safe_commands`: SAFE，只读或低风险命令。
- `review_commands`: CAUTION，需要人工复核。
- `blocked_commands`: DANGER，禁止执行。

## Evaluation

`reports/evaluation.md` 由 `evaluate --all` 生成，包含异常检测参数敏感性、多粒度窗口对比、RAG Chunking Recall@5、命令安全准确率、告警抑制说明和 10 倍日志量扩容分析。

离线评测不调用 Gemini，也不伪造 LLM 诊断质量分数。真实诊断报告的结构由 `DiagnosisService` 校验，命令建议会继续进入 SAFE / CAUTION / DANGER 分级；语义质量和 grounding 需要配置 `GEMINI_API_KEY` 后通过 `diagnose` 或 `/diagnose` 做真实验收。

## requirements.txt

依赖以 `pyproject.toml` 和 `uv.lock` 为准；`requirements.txt` 由 `uv export` 生成，仅作为交付物。
