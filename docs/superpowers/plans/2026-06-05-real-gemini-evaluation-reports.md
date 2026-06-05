# Real Gemini Evaluation Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Produce two independent Markdown reports: one from a real Gemini diagnosis run and one concise 10x log volume architecture evolution report.

**Architecture:** Reuse the existing CLI and LangGraph workflow. Do not change business code; generate or reuse deterministic logs, run `diagnose` to trigger Gemini, then write reports that separate online LLM validation from offline evaluation metrics.

**Tech Stack:** Python CLI via `uv`, existing `aiops_agent.interfaces.cli`, Gemini through `google-genai`, Markdown reports under `reports/`.

---

### Task 1: Real Gemini Diagnosis Evidence

**Files:**
- Read: `.env`
- Read: `src/aiops_agent/interfaces/cli.py`
- Create if absent: `data/logs/test_logs.jsonl`

- [x] **Step 1: Confirm Gemini environment without printing secrets**

Run: `if [ -f .env ]; then grep -q '^GEMINI_API_KEY=' .env && echo GEMINI_API_KEY_PRESENT; grep '^GEMINI_MODEL=' .env; else echo ENV_MISSING; fi`

Expected: output includes `GEMINI_API_KEY_PRESENT` and `GEMINI_MODEL=gemini-3.5-flash`.

- [x] **Step 2: Ensure deterministic input logs exist**

Run: `uv run python -m aiops_agent.interfaces.cli generate-data --seed 42 --per-service 220`

Expected: output path is `data/logs/test_logs.jsonl`.

- [x] **Step 3: Run real Gemini diagnosis**

Run: `uv run python -m aiops_agent.interfaces.cli diagnose data/logs/test_logs.jsonl --limit 350`

Expected: exit code 0 and JSON output includes `llm_report`, `safe_commands`, `review_commands`, `blocked_commands`, and `alert_decision`.

### Task 2: Write Gemini Evaluation Report

**Files:**
- Create: `reports/gemini_evaluation.md`

- [x] **Step 1: Write report from the real CLI output**

Use `apply_patch` to create `reports/gemini_evaluation.md` with these sections:

```markdown
# Gemini 真实调用评估报告

## 结论

## 执行信息

## 输入样本

## Gemini 结构化诊断

## 命令安全分级

## 告警抑制结果

## 验收判断

## 限制
```

The report must include only values observed in Task 1 output. It must state that `reports/evaluation.md` remains the offline reproducible metrics report.

- [x] **Step 2: Verify report contains required evidence**

Run: `rg -n "Gemini|llm_report|safe_commands|alert_decision|离线" reports/gemini_evaluation.md`

Expected: all five terms are present.

### Task 3: Write 10x Log Volume Architecture Report

**Files:**
- Create: `reports/tenfold_log_scale_architecture.md`

- [x] **Step 1: Write one-page architecture report**

Use `apply_patch` to create `reports/tenfold_log_scale_architecture.md` with these sections:

```markdown
# 「10 倍日志量扩容」架构演进方案

## 目标与约束

## 演进架构

## 关键策略

## 落地顺序

## 风险与观测
```

The report must describe ingestion, stream window aggregation, detection scaling, RAG/vector retrieval, Gemini call reduction, alert suppression, storage, and observability. Keep the file concise enough to fit on one printed page.

- [x] **Step 2: Verify report size and required topics**

Run: `wc -l reports/tenfold_log_scale_architecture.md && rg -n "Kafka|Flink|窗口|RAG|Gemini|告警|存储|监控" reports/tenfold_log_scale_architecture.md`

Expected: line count is under 45 and all topic terms are present.

### Task 4: Final Verification

**Files:**
- Read: `reports/gemini_evaluation.md`
- Read: `reports/tenfold_log_scale_architecture.md`

- [x] **Step 1: Confirm no API key was written**

Run: `rg -n "GEMINI_API_KEY|AIza|api_key|secret" reports docs/superpowers/specs docs/superpowers/plans`

Expected: no report contains a concrete API key; references to the environment variable name are acceptable only when they do not include the value.

- [x] **Step 2: Check changed files**

Run: `git status --short`

Expected: only the two reports and this plan are new or modified, plus any pre-existing unrelated untracked files.
