from aiops_agent.evaluation.rag_eval import evaluate_chunking_strategies, rag_test_queries
from aiops_agent.rag.chunkers import fixed_char_chunks, semantic_chunks
from aiops_agent.rag.k8s_loader import load_curated_k8s_docs


def test_k8s_docs_have_operational_topics():
    docs = load_curated_k8s_docs()
    titles = {doc["title"] for doc in docs}

    assert "Debug Pods" in titles
    assert "Resource Management" in titles
    assert "DNS Troubleshooting" in titles


def test_semantic_chunker_preserves_code_blocks():
    docs = [
        {
            "title": "Debug",
            "source": "local",
            "text": "## Debug\nRun:\n```bash\nkubectl get pods -A\n```\nThen inspect events.",
        }
    ]
    chunks = semantic_chunks(docs, target_size=80, overlap=10)

    assert any("kubectl get pods -A" in chunk.text for chunk in chunks)
    assert all(
        "```bash" in chunk.text and "```" in chunk.text or "```bash" not in chunk.text
        for chunk in chunks
    )


def test_rag_eval_returns_recall_for_two_strategies():
    docs = load_curated_k8s_docs()
    rows = evaluate_chunking_strategies(docs, rag_test_queries())

    assert {row["strategy"] for row in rows} == {"fixed", "semantic"}
    assert all("recall_at_5" in row for row in rows)
