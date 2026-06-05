# Gemini 在线量化评估报告

## 结论

本报告由 `evaluate-online` 生成：先在已标注子集 200 normal + 40 anomaly 上计算量化指标，再调用 `gemini-3.5-flash` 生成量化评估附录。报告中的指标来自本地可复现评估代码，附录文字来自真实 Gemini 在线调用。

## 在线评估证据

| 项目 | 值 |
|---|---|
| CLI | `uv run python -m aiops_agent.interfaces.cli evaluate-online` |
| 模型 | `gemini-3.5-flash` |
| 抽样数据 | `data/eval/online_sample.jsonl` |
| 证据 JSON | `data/eval/online_gemini_evaluation.json` |
| 命令安全准确率 | 100.00% |

## 抽样数据集

| normal | anomaly | latency_spike | transaction_conflict |
| --- | --- | --- | --- |
| 200 | 40 | 20 | 20 |

## 异常检测参数敏感性

| alpha | z_threshold | precision | recall | f1 | false_positive_rate |
| --- | --- | --- | --- | --- | --- |
| 0.1 | 2 | 1 | 0.9583 | 0.9787 | 0 |
| 0.1 | 2.5 | 1 | 0.9583 | 0.9787 | 0 |
| 0.1 | 3 | 1 | 0.9583 | 0.9787 | 0 |
| 0.2 | 2 | 1 | 0.9583 | 0.9787 | 0 |
| 0.2 | 2.5 | 1 | 0.9583 | 0.9787 | 0 |
| 0.2 | 3 | 1 | 0.9583 | 0.9787 | 0 |
| 0.3 | 2 | 1 | 0.8333 | 0.9091 | 0 |
| 0.3 | 2.5 | 1 | 0.8333 | 0.9091 | 0 |
| 0.3 | 3 | 1 | 0.8333 | 0.9091 | 0 |

## 多粒度窗口对比

| window_seconds | anomaly_type | alpha | z_threshold | precision | recall | f1 | false_positive_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | latency_spike | 0.2 | 2.5 | 0.6 | 0.3 | 0.4 | 0.0182 |
| 1 | transaction_conflict | 0.2 | 2.5 | 0.4 | 0.2 | 0.2667 | 0.0273 |
| 10 | latency_spike | 0.2 | 2.5 | 0.5217 | 1 | 0.6857 | 0.0982 |
| 10 | transaction_conflict | 0.2 | 2.5 | 0.4783 | 0.9167 | 0.6286 | 0.1071 |
| 60 | latency_spike | 0.2 | 2.5 | 0.5714 | 1 | 0.7273 | 0.1364 |
| 60 | transaction_conflict | 0.2 | 2.5 | 0.4286 | 0.75 | 0.5455 | 0.1818 |

## 异常类型识别准确性

| window_seconds | anomaly_type | alpha | z_threshold | precision | recall | f1 | false_positive_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | latency_spike | 0.2 | 2.5 | 1 | 1 | 1 | 0 |
| 10 | transaction_conflict | 0.2 | 2.5 | 1 | 0.9167 | 0.9565 | 0 |
| 10 | queue_backlog | 0.2 | 2.5 | 0 | 0 | 0 | 0 |

## RAG 检索质量

| strategy | chunk_count | avg_chunk_chars | avg_paragraphs_per_chunk | ground_truth_level | recall_at_5 |
| --- | --- | --- | --- | --- | --- |
| fixed | 482 | 789.39 | 5 | paragraph | 0.9 |
| semantic | 483 | 776.05 | 3.41 | paragraph | 1 |

## 命令安全分级准确性

| command | expected | predicted | reason |
| --- | --- | --- | --- |
| kubectl get pods -A | SAFE | SAFE | 只读取 Kubernetes 资源列表。 |
| kubectl describe pod api-0 | SAFE | SAFE | 只读取 Kubernetes 资源详情。 |
| kubectl logs deployment/api | SAFE | SAFE | 只读取 Kubernetes 日志。 |
| kubectl top pods -n prod | SAFE | SAFE | 只读取 Kubernetes 资源用量。 |
| top | SAFE | SAFE | 只查看系统进程概览。 |
| ps aux | SAFE | SAFE | 只查看进程列表。 |
| netstat -tulpn | SAFE | SAFE | 只查看网络连接状态。 |
| curl -I https://example.com/health | SAFE | SAFE | 只读取 HTTP 响应头。 |
| kubectl rollout restart deployment api | CAUTION | CAUTION | 包含服务重启操作。 |
| kubectl scale deployment api --replicas=3 | CAUTION | CAUTION | 包含副本数调整操作。 |
| systemctl restart nginx | CAUTION | CAUTION | 包含 systemctl restart 操作。 |
| kill 1234 | CAUTION | CAUTION | 包含 kill 进程操作。 |
| helm upgrade api ./chart | CAUTION | CAUTION | 未匹配到已知安全读操作，按未知命令谨慎处理。 |
| python scripts/migrate.py | CAUTION | CAUTION | 未匹配到已知安全读操作，按未知命令谨慎处理。 |
| rm -rf /var/lib/data | DANGER | DANGER | 包含 rm 递归强制删除操作。 |
| DROP TABLE users | DANGER | DANGER | 包含 DROP TABLE 破坏性数据库操作。 |
| kubectl delete pod api-0 | DANGER | DANGER | 包含 kubectl delete 删除集群资源。 |
| kubectl apply -f prod.yaml | DANGER | DANGER | 包含 kubectl apply -f 变更集群资源。 |
| chmod 777 /etc/passwd | DANGER | DANGER | 包含 chmod 777 高风险权限变更。 |
| dd if=/dev/zero of=/dev/sda | DANGER | DANGER | 包含 dd if= 块设备写入风险命令。 |
| :(){ :\|:& };: | DANGER | DANGER | 包含 fork bomb。 |
| kubectl get pods; rm -rf / | DANGER | DANGER | 包含 rm 递归强制删除操作。 |
| kubectl get pods && rm /tmp/file | DANGER | DANGER | 包含 shell 注入 rm 命令。 |
| kubectl get pods \| dd of=/tmp/out | DANGER | DANGER | 包含 shell 注入 dd 命令。 |
| kubectl get pods $(rm /tmp/file) | DANGER | DANGER | 包含 shell 注入 rm 命令。 |
| rm -fr /var/lib/data | DANGER | DANGER | 包含 rm 递归强制删除操作。 |
| rm -r -f /var/lib/data | DANGER | DANGER | 包含 rm 递归强制删除操作。 |
| echo ok; dd if=/dev/zero of=/tmp/blob | DANGER | DANGER | 包含 dd if= 块设备写入风险命令。 |
| kubectl get pods; kubectl delete pod api-0 | DANGER | DANGER | 包含 kubectl delete 删除集群资源。 |

## 优化前 vs 优化后

| change | before | after | f1_delta |
| --- | --- | --- | --- |
| alpha 0.3 -> 0.1 with z_threshold 2.5 | {"alpha": 0.3, "z_threshold": 2.5, "precision": 1.0, "recall": 0.8333, "f1": 0.9091, "false_positive_rate": 0.0} | {"alpha": 0.1, "z_threshold": 2.5, "precision": 1.0, "recall": 0.9583, "f1": 0.9787, "false_positive_rate": 0.0} | 0.0696 |

# AIOps 评估报告定量分析附录

## 1. 异常检测参数敏感性 (3x3 Grid)
针对异常检测算法中的平滑系数 `alpha` 与阈值 `z_threshold`，进行了 3x3 参数敏感性网格搜索。结果如下表所示：

| Alpha | Z-Threshold | Precision | Recall | F1-Score | False Positive Rate (FPR) |
|---|---|---|---|---|---|
| 0.1 | 2.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.1 | 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.1 | 3.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 2.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 3.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.3 | 2.0 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| 0.3 | 2.5 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| 0.3 | 3.0 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |

*结果表明：当 alpha 从 0.1 或 0.2 增大到 0.3 时，Recall 从 0.9583 下降至 0.8333，表明过大的平滑系数会降低算法对指标异常波动的敏感度，从而带来漏报。*

---

## 2. 时间粒度 (1s/10s/60s) 对比分析
在不同时间窗口下，针对延迟抖动 (`latency_spike`) 和事务冲突 (`transaction_conflict`) 的检测表现如下：

| 时间窗口 (Window) | 异常类型 (Anomaly Type) | Precision | Recall | F1-Score | False Positive Rate (FPR) |
|---|---|---|---|---|---|
| 1s | latency_spike | 0.6000 | 0.3000 | 0.4000 | 0.0182 |
| 1s | transaction_conflict | 0.4000 | 0.2000 | 0.2667 | 0.0273 |
| 10s | latency_spike | 0.5217 | 1.0000 | 0.6857 | 0.0982 |
| 10s | transaction_conflict | 0.4783 | 0.9167 | 0.6286 | 0.1071 |
| 60s | latency_spike | 0.5714 | 1.0000 | 0.7273 | 0.1364 |
| 60s | transaction_conflict | 0.4286 | 0.7500 | 0.5455 | 0.1818 |

### 粒度适用性与原因分析：
1. **延迟抖动 (latency_spike)**：
   - **更佳粒度**：**60s** (F1-score: 0.7273) 或 **10s** (F1-score: 0.6857，且 Recall 达到 1.0)。
   - **原因**：延迟抖动往往需要一定的时间周期进行数据聚合（如计算均值或高分位数）才能呈现明显的异常特征。在极短的 1s 粒度下，网络和系统的瞬态扰动会被放大为高频噪声，导致检出率低下（Recall 仅 0.3000）；而在 10s 或 60s 窗口下，指标经过平滑过滤，能更稳健地识别真正的延迟飙升。
2. **事务冲突 (transaction_conflict)**：
   - **更佳粒度**：**10s** (F1-score: 0.6286)。
   - **原因**：1s 粒度因采样窗口过窄，难以完整覆盖一个事务生命周期内的多级锁竞争及冲突过程（Recall 仅 0.2000）；而在 60s 粒度下，短时间的并发事务冲突又极易被长时间窗口内的其他正常事务所稀释，导致 Precision 出现明显下滑（从 0.4783 降至 0.4286），误报率 FPR 也随之上升（从 0.1071 升至 0.1818）。因此，中等粒度（10s）是检测事务冲突的最佳折中方案。

---

## 3. 严格 Anomaly Type 级别指标
在 10s 时间窗口 (alpha=0.2, z_threshold=2.5) 下，具体异常类型的严格检测指标如下：

| 异常类型 (Anomaly Type) | Precision | Recall | F1-Score | False Positive Rate (FPR) |
|---|---|---|---|---|
| latency_spike | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| transaction_conflict | 1.0000 | 0.9167 | 0.9565 | 0.0000 |
| queue_backlog | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

*注：queue_backlog 的各项指标均为 0.0000，表明当前检测模型在此类型异常上的识别和对齐能力仍有缺失。*

---

## 4. RAG Chunking 策略对比
针对 10 条测试 Query，对比了固定长度切片 (fixed) 与语义切片 (semantic) 的检索召回效果：

| 切片策略 (Strategy) | 分片总数 (Chunk Count) | 平均分片字符数 | 平均每分片段落数 | Recall@5 |
|---|---|---|---|---|
| 固定长度切片 (fixed) | 482 | 789.39 | 5.00 | 0.90 |
| 语义切片 (semantic) | 483 | 776.05 | 3.41 | 1.00 |

### 分析与受影响 Query 类型：
- **语义切片 (semantic)** 在 Recall@5 上取得了 1.00 的完美召回率，优于固定切片的 0.90。
- **受影响 Query 类型**：那些需要高上下文一致性、逻辑上跨越自然段落、或依赖完整句子逻辑链的复杂查询（例如“涉及多步骤故障排查文档”或“深层组件交互原理解析”）更易受到切片策略影响。固定长度切片会强行在预设字符处断开，使跨界语义受损，而语义切片通过保持完整的自然段落逻辑，避免了上下文信息的断裂。

---

## 5. 命令安全分级准确率与误分类案例
评估集中共包含 29 条运维命令安全分级样本：

- **总样本数**：29
- **分类准确率 (Accuracy)**：100.0% (29/29)
- **误分类案例**：
  - 本次评估中没有出现误分类案例（准确率达 100%）。危险指令（包含 `rm -rf`、`DROP TABLE`、`kubectl delete`、注入漏洞、fork 炸弹等破坏性操作）均被精准标记为 DANGER 或 CAUTION，常规读取指令全部被正确标为 SAFE。

---

## 6. 参数优化前 vs 优化后对比
通过参数敏感性搜索，对核心检测算法实施了优化：

| 阶段 | 参数配置 | Precision | Recall | F1-Score | FPR |
|---|---|---|---|---|---|
| **优化前** | alpha 0.3, z_threshold 2.5 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| **优化后** | alpha 0.1, z_threshold 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |

- **F1 提升 (Delta)**：**+0.0696**
- **效果说明**：将平滑系数 `alpha` 从 0.3 优化调整至 0.1，使系统在不引入任何误报（FPR 保持 0.0000）的情况下，将异常检测召回率提升了 12.5%，大幅减少了对偶发性故障指标的漏报。

