from __future__ import annotations

from aiops_agent.evaluation.metrics import recall_at_k
from aiops_agent.models.schemas import TextChunk
from aiops_agent.rag.chunkers import fixed_char_chunks, semantic_chunks
from aiops_agent.rag.vector_store import SimpleVectorStore


def rag_test_queries() -> list[dict[str, object]]:
    return [
        {
            "query": "how to inspect pod events for latency spike",
            "expected_titles": {"Debug Pods", "Events"},
        },
        {
            "query": "cpu throttling causes high latency in pods",
            "expected_titles": {"Resource Management"},
        },
        {
            "query": "readiness probe failures remove pods from service",
            "expected_titles": {"Probes"},
        },
        {
            "query": "service DNS lookup timeouts in Kubernetes",
            "expected_titles": {"DNS Troubleshooting"},
        },
        {
            "query": "check deployment rollout status",
            "expected_titles": {"Deployments"},
        },
        {
            "query": "kubectl logs for application timeout",
            "expected_titles": {"Debug Pods"},
        },
        {
            "query": "cluster events sorted by timestamp",
            "expected_titles": {"Events"},
        },
        {
            "query": "memory limits and OOM diagnostic",
            "expected_titles": {"Resource Management"},
        },
        {
            "query": "CoreDNS pods logs troubleshooting",
            "expected_titles": {"DNS Troubleshooting"},
        },
        {
            "query": "liveness probe restarts unhealthy container",
            "expected_titles": {"Probes"},
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
            expected_titles = set(query["expected_titles"])
            retrieved_titles = [item.title for item in retrieved]
            recalls.append(recall_at_k(expected_titles, retrieved_titles, k=5))

        rows.append(
            {
                "strategy": strategy,
                "chunk_count": len(chunks),
                "avg_chunk_chars": _avg_chunk_chars(chunks),
                "recall_at_5": _avg(recalls),
            }
        )

    return rows


def _avg_chunk_chars(chunks: list[TextChunk]) -> float:
    if not chunks:
        return 0.0
    return round(sum(len(chunk.text) for chunk in chunks) / len(chunks), 2)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
