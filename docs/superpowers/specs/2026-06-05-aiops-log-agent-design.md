# AI 运维日志异常检测 Agent 设计文档

日期：2026-06-05

## 1. 背景与目标

本项目在新场景中复现 DB-LogAnalyzer 的核心技术思路，面向一个包含 5 个微服务的 SaaS 运维场景，建立从日志异常检测、RAG 检索、Gemini 诊断、命令安全分级到量化评估报告的完整闭环。

目标不是构建复杂线上平台，而是交付一个评测优先、可复现、可解释的 Agent 原型。所有关键结论必须能通过数据集和评测脚本重新生成，避免只靠人工描述。

核心成功标准：

- 构建带标注的 JSONL 日志数据集，覆盖正常日志和 3 类异常。
- 实现 EWMA + Z-Score 异常检测，并完成 `alpha × z_threshold` 参数敏感性分析。
- 实现 1s / 10s / 60s 多粒度窗口对比。
- 基于 Kubernetes 官方文档构建 RAG 语料，比较两种 chunking 策略的 Recall@5。
- 通过 LangGraph 编排诊断 workflow，真实调用 Gemini `gemini-3.5-flash`。
- 实现 SAFE / CAUTION / DANGER 命令安全分级，并量化准确率。
- 实现 60 秒告警抑制和 asyncio 流式检测。
- 生成 Markdown 评测报告和图表。

## 2. 明确假设

- 项目目录为 `/Users/haofu/workspace/xiaodai/interview/aiops-log-agent`。
- Gemini API key 写入未提交的 `.env`，提交仓库只包含 `.env.example`。
- RAG 语料选 Kubernetes 官方文档中与运维排障相关的子集，不全站抓取。
- 向量库使用 ChromaDB，embedding 使用本地 `sentence-transformers/all-MiniLM-L6-v2`，Gemini 只用于最终诊断生成。
- 日志数据采用固定随机种子的合成数据，便于复现实验数字。
- LangGraph 只负责编排；检测、RAG、LLM、安全、告警等业务逻辑放到 service 层。

## 3. 非目标

- 不实现完整生产级观测平台。
- 不接入真实 Kubernetes 集群执行命令。
- 不让 LLM 直接决定异常是否存在。
- 不让 LLM 绕过命令安全分级。
- 不实现复杂权限系统、用户系统或前端 Dashboard。

## 4. 项目目录

```text
aiops-log-agent/
  src/aiops_agent/
    graph/
      state.py
      builder.py
      nodes.py
      routing.py

    services/
      log_service.py
      detection_service.py
      rag_service.py
      llm_service.py
      safety_service.py
      alert_service.py
      diagnosis_service.py

    data/
      generator.py
      schemas.py

    detection/
      ewma.py
      zscore.py
      windows.py

    rag/
      chunkers.py
      vector_store.py
      k8s_loader.py

    evaluation/
      metrics.py
      anomaly_eval.py
      rag_eval.py
      safety_eval.py
      report_writer.py

    interfaces/
      cli.py
      api.py
      stream.py

    config.py

  data/
    logs/
    rag/
    eval/

  reports/
    figures/
    evaluation.md

  docs/
    contexts/
    superpowers/
      specs/

  tests/
  .env
  .env.example
  .gitignore
  pyproject.toml
  uv.lock
  requirements.txt
  README.md
```

`graph/` 与 `services/` 必须保持边界清晰。Graph 节点只做状态读写和调用 service，不写检测算法、RAG 细节或 Gemini prompt 拼装逻辑。

节点与 service 对应关系：

```text
parse_input_node       -> LogService
detect_anomalies_node  -> DetectionService
retrieve_docs_node     -> RAGService
gemini_diagnose_node   -> GeminiLLMService
classify_commands_node -> CommandSafetyService
suppress_alerts_node   -> AlertService
format_response_node   -> DiagnosisService
```

## 5. LangGraph Workflow

使用 LangGraph `StateGraph` 定义诊断流程。状态对象 `AIOpsDiagnosisState` 保存端到端上下文：

```text
log_snippet
detected_anomalies
window_metrics
rag_query
retrieved_chunks
llm_report
suggested_commands
safe_commands
blocked_commands
alert_decision
errors
```

主流程：

```text
START
  -> parse_input
  -> detect_anomalies
  -> build_rag_query
  -> retrieve_k8s_docs
  -> gemini_diagnose
  -> classify_commands
  -> suppress_alerts
  -> format_response
  -> END
```

CLI、FastAPI `/diagnose` 和 asyncio stream 都调用同一个 compiled graph，避免三套流程漂移。评测脚本可以直接调用 service，也可以用 graph 做端到端冒烟测试。

## 6. 数据集设计

日志数据为 JSONL，每条日志包含：

```text
timestamp, service, latency_ms, error_code, request_id,
endpoint, status_code, cpu_pct, memory_mb, queue_depth,
dependency, anomaly_type, is_anomaly
```

服务列表：

```text
api-gateway
auth-service
business-service
data-service
message-queue
```

规模：

- 每个服务至少 200 条日志。
- 整体约 1,000 到 1,200 条日志。
- 至少 200 条正常日志。
- 至少 40 条已标注异常日志。
- 3 种异常类型各至少 10 条，实际生成时优先每类 30 到 50 条，保证 F1 更稳定。

异常类型：

1. `latency_spike`：短时间高延迟尖峰，主要考察 1s / 10s 窗口与 EWMA 响应速度。
2. `transaction_conflict`：中等延迟持续升高并伴随 `409/CONFLICT` 增加，主要考察 10s / 60s 窗口。
3. `queue_backlog`：队列积压拖高链路延迟，考察跨服务关联和告警抑制。

标注策略：

- 单条日志使用 `is_anomaly` 和 `anomaly_type` 做 Precision / Recall / F1。
- 窗口级评估中，只要窗口内存在异常日志，该窗口即为正样本。
- 告警抑制评估按 `service + anomaly_type + root_cause` 判断重复告警。

## 7. 异常检测与参数标定

检测流程：

```text
日志
  -> 按 service + window 聚合 latency_ms
  -> EWMA 平滑
  -> 基于残差或窗口均值计算 Z-Score
  -> 输出异常窗口和异常日志映射
```

参数扫描：

```text
alpha:       0.1, 0.2, 0.3
z_threshold: 2.0, 2.5, 3.0
window:      1s, 10s, 60s
```

输出指标：

- 9 组 `alpha × z_threshold` 的 Precision / Recall / F1 / FPR。
- 1s / 10s / 60s 在 `latency_spike` 和 `transaction_conflict` 上的 F1。
- F1 热力图、阈值折线图、窗口粒度柱状图。

参数解释：

- `alpha=0.1` 更平滑，抗噪声更强，但对短 spike 响应较慢。
- `alpha=0.3` 响应更快，但基线更容易被异常拖动，误报可能增加。
- `alpha=0.2` 是候选折中值，最终选择由评测数据决定。
- `z_threshold=2.0` 更敏感，召回高但误报可能上升。
- `z_threshold=3.0` 更保守，误报低但漏报风险更高。

最终推荐参数不硬编码，评测脚本按 F1 和 FPR 共同选择。

## 8. Kubernetes RAG 与 Chunking 评估

Kubernetes 官方文档选取排障相关子集：

```text
Pods / Deployments / Services
Troubleshooting Applications
Debug Pods and Nodes
Resource Management
Probes
Events
DNS / Networking
Jobs / CronJobs
```

Chunking 策略 A：固定字符长度。

```text
chunk_size = 800 chars
overlap = 120 chars
```

Chunking 策略 B：语义边界切分。

```text
按标题、段落、列表、代码块切分
目标 chunk_size ~= 900 chars
overlap ~= 150 chars
代码块和命令示例不拆开
标题路径写入 metadata
```

评测：

- 构建 10 条 Kubernetes 运维 query。
- 每条人工标注 1 到 3 个相关文档段落或 chunk id。
- 分别用策略 A/B 建库，计算 Recall@5。
- 报告输出 chunk 数量、chunk 长度分布、Recall@5 对比表和 bad case 分析。

RAG 在诊断中的作用：

```text
异常摘要 -> 构造检索 query -> Top-5 Kubernetes chunks
        -> Gemini 3.5 Flash 生成结构化诊断
```

Gemini prompt 必须要求引用检索片段，不允许脱离 RAG 直接给诊断建议。

## 9. Gemini 诊断

Gemini 配置：

```text
GEMINI_MODEL=gemini-3.5-flash
GEMINI_API_KEY=<local .env only>
```

`GeminiLLMService` 调用真实 Gemini API，输出结构化 JSON：

```json
{
  "anomaly_type": "latency_spike",
  "likely_root_causes": ["pod resource saturation"],
  "evidence": ["latency p95 increased in api-gateway 10s window"],
  "recommended_commands": ["kubectl get pods -A", "kubectl describe pod <pod> -n <namespace>"],
  "confidence": 0.82
}
```

若 Gemini 返回非 JSON，`DiagnosisService` 负责做一次结构化校验和错误报告，不静默吞掉错误。

## 10. 命令安全分级

命令安全分级采用规则优先和正则匹配，不依赖 LLM 分类。安全闸门必须确定、可审计、可量化。

分级：

- `SAFE`：只读命令，例如 `kubectl get`、`kubectl describe`、`kubectl logs`、`top`、`ps`、`netstat`、`curl -I`。
- `CAUTION`：可能改变状态或影响服务，例如 `kubectl rollout restart`、`kubectl scale`、`systemctl restart`、`kill`。
- `DANGER`：破坏性或高风险，例如 `rm -rf`、`DROP TABLE`、`kubectl delete`、未确认的 `kubectl apply -f`、`chmod 777`、`dd`、fork bomb 模式。

处理规则：

- Gemini 产出的所有命令必须进入 `CommandSafetyService`。
- `DANGER` 命令不展示为可执行建议，只进入 `blocked_commands` 并说明拦截原因。
- `CAUTION` 命令保留，但标记为需要人工确认。
- CLI 和 `/diagnose` 输出都显示安全等级。

评测：

- 构建 20 条命令测试集，三级各至少 6 条。
- 报告准确率、混淆矩阵和误分类案例。
- 做一次“优化前 vs 优化后”：baseline 只用关键词，优化版加入命令前缀、危险 flag、管道组合和 shell 注入正则。

## 11. 告警抑制与 asyncio 流式处理

流式入口：

```text
uv run python -m aiops_agent.interfaces.cli stream data/logs/test_logs.jsonl --window 10 --emit-interval 1
```

流程：

```text
async log reader
  -> async window buffer
  -> DetectionService.incremental_detect()
  -> LangGraph diagnosis workflow
  -> AlertService.suppress()
  -> stdout 输出告警或抑制结果
```

实时目标：

- 每 1 秒 flush 当前窗口。
- 新异常在 1 秒内输出告警。
- 对相同 `service + anomaly_type + root_cause`，60 秒内只保留第一条告警。

告警抑制评测：

```text
raw_alert_count
suppressed_alert_count
final_alert_count
noise_reduction_rate
```

## 12. CLI 与 API

CLI 子命令：

```text
generate-data
evaluate --all
diagnose <log_file> --limit 80
stream <log_file> --window 10 --emit-interval 1
build-rag
```

FastAPI：

```text
POST /diagnose
```

请求体包含异常日志片段或日志文件内容，响应体为 LangGraph 最终状态中的结构化诊断结果。

## 13. 评测报告

报告由脚本生成：

```text
uv run python -m aiops_agent.interfaces.cli evaluate --all
```

输出：

- `reports/evaluation.md`
- `reports/figures/f1_heatmap.png`
- `reports/figures/window_f1_comparison.png`
- `reports/figures/rag_recall_at_5.png`
- `reports/figures/safety_confusion_matrix.png`

报告内容：

- 异常检测参数敏感性：9 组配置表 + 图表。
- 多窗口对比：1s / 10s / 60s 在两类重点异常上的 F1。
- RAG 质量：两种 chunking 的 chunk 数量分布和 10 条 query Recall@5。
- 命令安全：20 条命令准确率、混淆矩阵、bad cases。
- 告警抑制：优化前后告警数量与降噪率。
- 10 倍日志量扩容方案：不超过 1 页。

10 倍日志量扩容判断：

- 当前瓶颈是 Python 单进程窗口聚合、Chroma 本地检索、Gemini 调用延迟。
- 10K logs/min 后，日志读取和窗口聚合应分片到 Kafka/Flink 或 asyncio 多 worker。
- 向量检索迁移为持久化/服务化向量库。
- Gemini 诊断只对抑制后的代表告警触发，避免每条异常都调用 LLM。

## 14. 测试计划

```text
tests/
  test_detection.py
  test_rag_chunking.py
  test_safety.py
  test_alerting.py
  test_graph.py
  test_cli_smoke.py
```

测试重点：

- EWMA、Z-Score、窗口聚合和参数扫描输出稳定。
- 固定切分和语义切分能生成可评测 chunk。
- 命令安全分级覆盖 SAFE / CAUTION / DANGER。
- 告警抑制 60 秒窗口逻辑正确。
- LangGraph 节点按预期读写 state。
- CLI 关键命令可运行。

## 15. 交付验收

验收命令：

```text
uv sync
uv run pytest
uv run python -m aiops_agent.interfaces.cli generate-data
uv run python -m aiops_agent.interfaces.cli build-rag
uv run python -m aiops_agent.interfaces.cli evaluate --all
uv run python -m aiops_agent.interfaces.cli diagnose data/logs/test_logs.jsonl --limit 80
uv run python -m aiops_agent.interfaces.cli stream data/logs/test_logs.jsonl --window 10 --emit-interval 1
uv export --format requirements.txt --no-hashes --no-emit-project --output-file requirements.txt
```

验收条件：

- 测试通过。
- 评测报告和图表生成。
- `diagnose` 真实调用 Gemini `gemini-3.5-flash`。
- `/diagnose` 与 CLI 共享同一个 LangGraph workflow。
- `.env` 不被提交。
- README 说明启动、评测和关键设计。
- 代码关键逻辑包含必要中文注释。

## 16. 风险与取舍

- Gemini API 可能有网络或配额失败；CLI 应清晰报错，不伪造诊断结果。
- 语义 chunking 实现不能过度复杂，优先保证标题、段落、代码块不被破坏。
- 合成数据可能不代表真实线上分布；报告需要说明边界。
- LangGraph 增加依赖和结构成本，但能清晰展示 agentic workflow 和状态流转。
- 为保证 1 天交付，Dashboard 和多模型对比暂不纳入本设计。

## 17. 参考资料

- Gemini 模型文档：https://ai.google.dev/gemini-api/docs/models
- LangGraph StateGraph 文档：https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- LangGraph Graph API 文档：https://docs.langchain.com/oss/python/langgraph/use-graph-api
- Kubernetes 官方文档：https://kubernetes.io/docs/
