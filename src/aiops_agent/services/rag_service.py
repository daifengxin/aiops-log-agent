from __future__ import annotations

from pathlib import Path

from aiops_agent.models.schemas import DetectedAnomaly, RetrievedChunk
from aiops_agent.rag.chunkers import semantic_chunks
from aiops_agent.rag.k8s_loader import load_curated_k8s_docs
from aiops_agent.rag.vector_store import ChromaVectorStore


class RAGService:
    """构造 Kubernetes 排障查询并执行语义检索。"""

    def __init__(self, persist_dir: Path | None = None) -> None:
        chunks = semantic_chunks(load_curated_k8s_docs())
        self.store = ChromaVectorStore(persist_dir or Path("data/rag/chroma"))
        self.store.rebuild(chunks)

    def build_query(self, anomalies: list[DetectedAnomaly]) -> str:
        if not anomalies:
            return "kubernetes troubleshooting latency errors pods events"

        # 只取前几个异常，避免一次查询被长时间窗口日志稀释。
        parts = [
            f"{item.service} {item.anomaly_type} {item.metric_name} {item.reason}"
            for item in anomalies[:5]
        ]
        return " ".join(parts) + " kubernetes kubectl troubleshooting"

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        return self.store.query(query, top_k=top_k)
