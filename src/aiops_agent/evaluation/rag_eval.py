from __future__ import annotations

from aiops_agent.evaluation.metrics import recall_at_k
from aiops_agent.models.schemas import TextChunk
from aiops_agent.rag.chunkers import fixed_char_chunks, semantic_chunks
from aiops_agent.rag.vector_store import SimpleVectorStore


def rag_test_queries() -> list[dict[str, object]]:
    return [
        {
            "query": "how to inspect pod events for latency spike",
            "expected_paragraph_ids": {"Events#p3"},
        },
        {
            "query": "cpu throttling causes high latency in pods",
            "expected_paragraph_ids": {"Resource Management#p6"},
        },
        {
            "query": "readiness probe failures remove pods from service",
            "expected_paragraph_ids": {"Probes#p40"},
        },
        {
            "query": "service DNS lookup timeouts in Kubernetes",
            "expected_paragraph_ids": {"Services#p185"},
        },
        {
            "query": "check deployment rollout status",
            "expected_paragraph_ids": {"Deployments#p240"},
        },
        {
            "query": "kubectl logs for application timeout",
            "expected_paragraph_ids": {"kubectl Logs#p0"},
        },
        {
            "query": "cluster events sorted by timestamp",
            "expected_paragraph_ids": {"Events#p1"},
        },
        {
            "query": "memory limits and OOM diagnostic",
            "expected_paragraph_ids": {"Resource Management#p7"},
        },
        {
            "query": "CoreDNS pods logs troubleshooting",
            "expected_paragraph_ids": {"DNS Troubleshooting#p56"},
        },
        {
            "query": "liveness probe restarts unhealthy container",
            "expected_paragraph_ids": {"Probes#p20"},
        },
    ]


def evaluate_chunking_strategies(
    docs: list[dict[str, str]],
    queries: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    strategies = {
        "fixed": fixed_char_chunks(docs),
        "semantic": semantic_chunks(docs),
    }

    for strategy, chunks in strategies.items():
        store = SimpleVectorStore(chunks)
        recalls: list[float] = []
        for query in queries:
            retrieved = store.query(str(query["query"]), top_k=5)
            expected_ids = _expected_ids(query)
            retrieved_ids = _retrieved_ids(retrieved, "paragraph")
            # Recall@5 的 5 指 Top-5 chunk；一个 chunk 可能覆盖多个段落，因此先展开段落 ID。
            recalls.append(recall_at_k(expected_ids, retrieved_ids, k=len(retrieved_ids)))

        rows.append(
            {
                "strategy": strategy,
                "chunk_count": len(chunks),
                "avg_chunk_chars": _avg_chunk_chars(chunks),
                "avg_paragraphs_per_chunk": _avg_paragraphs_per_chunk(chunks),
                "ground_truth_level": "paragraph",
                "recall_at_5": _avg(recalls),
            }
        )

    return rows


def _expected_ids(query: dict[str, object]) -> set[str]:
    ids = query.get("expected_paragraph_ids")
    if ids is None:
        ids = query.get("expected_titles", set())
    return {str(item) for item in ids}


def _retrieved_ids(retrieved: list[object], ground_truth_level: str) -> list[str]:
    if ground_truth_level != "paragraph":
        return [str(getattr(item, "title")) for item in retrieved]

    ids: list[str] = []
    for item in retrieved:
        ids.extend(str(paragraph_id) for paragraph_id in item.paragraph_ids)
    return ids


def _avg_chunk_chars(chunks: list[TextChunk]) -> float:
    if not chunks:
        return 0.0
    return round(sum(len(chunk.text) for chunk in chunks) / len(chunks), 2)


def _avg_paragraphs_per_chunk(chunks: list[TextChunk]) -> float:
    if not chunks:
        return 0.0
    return round(sum(len(chunk.paragraph_ids) for chunk in chunks) / len(chunks), 2)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
