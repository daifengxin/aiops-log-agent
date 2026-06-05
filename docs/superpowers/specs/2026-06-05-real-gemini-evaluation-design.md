# 真实 Gemini 评估报告与 10 倍扩容报告设计

日期：2026-06-05

## 背景

当前 `reports/evaluation.md` 是离线评估报告，`write_full_report` 明确不触发 Gemini 或网络调用。项目已经具备真实 Gemini 调用路径：`diagnose` CLI 通过 LangGraph 执行检测、RAG、Gemini 诊断、命令安全分级和告警抑制。

本次目标是补齐两份独立报告，避免把离线可复现指标和在线 LLM 验收混在同一个文件里。

## 范围

新增两份报告：

- `reports/gemini_evaluation.md`：记录一次真实 Gemini 调用的诊断验收结果。
- `reports/tenfold_log_scale_architecture.md`：单独描述「10 倍日志量扩容」架构演进方案，内容控制在 1 页内。

保留现有 `reports/evaluation.md`，不覆盖离线报告。

## 执行设计

1. 真实 Gemini 评估
   - 使用 `.env` 中的 `GEMINI_API_KEY` 和 `GEMINI_MODEL`。
   - 如缺少输入日志，先用现有 `generate-data` CLI 生成确定性测试日志。
   - 用现有 `diagnose` CLI 执行真实诊断，保留结构化输出。
   - 报告写明执行命令、模型名、输入样本规模、Gemini 结构化诊断摘要、安全分级结果、告警抑制结果和限制。

2. 10 倍日志量扩容方案
   - 从当前单机原型出发，描述扩容后的 ingestion、流式窗口聚合、检测服务、RAG/向量库、Gemini 调用削峰、告警抑制、存储和监控。
   - 强调减少 Gemini 调用次数：只对抑制后的代表告警触发 LLM，不对每条异常日志调用。
   - 控制篇幅小于 1 页，适合作为面试交付报告附件。

## 验证标准

- `reports/gemini_evaluation.md` 存在，并包含真实 CLI 输出中的 `llm_report` 诊断结果。
- Gemini 报告明确说明它不是离线指标报告，而是一次真实在线调用验收。
- `reports/tenfold_log_scale_architecture.md` 存在，内容独立且小于 1 页。
- 运行相关 CLI 成功；如 Gemini 调用失败，报告不得伪造结果，必须记录失败原因。

## 非目标

- 不修改现有检测、RAG、安全分级算法。
- 不新增生产级队列、流处理或向量数据库代码。
- 不把 Gemini 语义质量包装成离线可复现分数。
- 不提交 `.env` 或泄露 API key。
