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

## RAG 检索质量

| strategy | chunk_count | avg_chunk_chars | recall_at_5 |
| --- | --- | --- | --- |
| fixed | 14 | 566.36 | 1 |
| semantic | 14 | 566.36 | 1 |

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

### 1. 异常检测参数敏感性分析 (3x3 Grid)

在不同平滑系数 $\alpha$ (alpha) 和阈值 $z\_threshold$ 组合下，异常检测的指标表现如下：

| $\alpha$ (alpha) | $z\_threshold$ | Precision | Recall | F1-Score | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0.1 | 2.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.1 | 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.1 | 3.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 2.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.2 | 3.0 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| 0.3 | 2.0 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| 0.3 | 2.5 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| 0.3 | 3.0 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |

### 2. 不同时间粒度下的异常检测对比 (1s / 10s / 60s)

| 时间粒度 (Window) | 异常类型 (Anomaly Type) | Precision | Recall | F1-Score | FPR |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1s | latency_spike | 0.6000 | 0.3000 | 0.4000 | 0.0182 |
| 1s | transaction_conflict | 0.4000 | 0.2000 | 0.2667 | 0.0273 |
| 10s | latency_spike | 0.5217 | 1.0000 | 0.6857 | 0.0982 |
| 10s | transaction_conflict | 0.4783 | 0.9167 | 0.6286 | 0.1071 |
| 60s | latency_spike | 0.5714 | 1.0000 | 0.7273 | 0.1364 |
| 60s | transaction_conflict | 0.4286 | 0.7500 | 0.5455 | 0.1818 |

**粒度适用性及原因分析：**
*   **延迟突增 (latency_spike)**：**60s 粒度更适合**（F1-Score 达到最高值 0.7273，Recall 为 1.0000）。延迟突增在较长的时间窗口内可以呈现出更明显的统计对比特征，而极短窗口（如 1s）容易受到突发毛刺的瞬时波动干扰，导致召回率极低（Recall 仅 0.3000）。
*   **事务冲突 (transaction_conflict)**：**10s 粒度更适合**（F1-Score 达到最高值 0.6286，Recall 为 0.9167）。事务冲突具有时效性。当窗口延长到 60s 时，局部的冲突特征容易被长周期内的正常事务所稀释，导致召回率下降至 0.7500，F1-Score 跌至 0.5455。而 1s 窗口过短，无法捕获一个完整事务冲突周期的度量表现，导致 Recall 仅为 0.2000。

### 3. RAG 分块策略评估

针对 10 条 Query，评估了两种不同的 chunking 策略在 Recall@5 上的表现：

| 分块策略 (Strategy) | 分块数量 (Chunk Count) | 平均分块字数 (Avg Chars) | Recall@5 |
| :--- | :--- | :--- | :--- |
| 固定长度分块 (fixed) | 14 | 566.36 | 1.0000 |
| 语义分块 (semantic) | 14 | 566.36 | 1.0000 |

**影响分析：**
在本测试集的 10 条 Query 中，无论是固定长度分块还是语义分块，其 Recall@5 均达到了 **1.0 (100%)**。这表明在该样本规模及参数配置下，两种策略的表现同样优异，**没有特定类型的 Query 受到分块策略的不利影响**。

### 4. 命令安全分级准确率与案例分析

*   **总评估命令条数**：29 条
*   **分类准确率**：100% (29/29)
*   **误分类案例**：无 (0 个误分类案例)

**典型安全分级案例展示：**
*   **SAFE（安全）案例**：
    *   `kubectl get pods -A` -> 预测：`SAFE`（原因：只读取 Kubernetes 资源列表。）
    *   `top` -> 预测：`SAFE`（原因：只查看系统进程概览。）
*   **CAUTION（警告）案例**：
    *   `systemctl restart nginx` -> 预测：`CAUTION`（原因：包含 systemctl restart 操作。）
    *   `kubectl rollout restart deployment api` -> 预测：`CAUTION`（原因：包含服务重启操作。）
*   **DANGER（危险）案例**：
    *   `rm -rf /var/lib/data` -> 预测：`DANGER`（原因：包含 rm 递归强制删除操作。）
    *   `DROP TABLE users` -> 预测：`DANGER`（原因：包含 DROP TABLE 破坏性数据库操作。）
    *   `kubectl get pods && rm /tmp/file` -> 预测：`DANGER`（原因：包含 shell 注入 rm 命令。）

### 5. 异常检测算法优化对比

针对异常检测算法中的参数配置进行了优化对比（优化前 vs 优化后）：

| 阶段 | 参数配置 | Precision | Recall | F1-Score | False Positive Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **优化前 (Before)** | alpha = 0.3, z_threshold = 2.5 | 1.0000 | 0.8333 | 0.9091 | 0.0000 |
| **优化后 (After)** | alpha = 0.1, z_threshold = 2.5 | 1.0000 | 0.9583 | 0.9787 | 0.0000 |
| **差值 (Delta)** | alpha 0.3 -> 0.1 | 0.0000 | +0.1250 | **+0.0696** | 0.0000 |

**优化结论**：
通过调整参数，平滑系数 `alpha` 从 0.3 降低到 0.1（保持 `z_threshold` 在 2.5），召回率（Recall）从 0.8333 提升至 0.9583，从而促使 **F1-Score 提升了 0.0696**（即 6.96% 的绝对 F1 提升），同时保持了 0.0 的零误报率（False Positive Rate），显著优化了检测系统的敏感度与稳定性。

