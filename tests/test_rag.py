import pytest

from aiops_agent.evaluation.rag_eval import evaluate_chunking_strategies, rag_test_queries
from aiops_agent.models.schemas import TextChunk
from aiops_agent.rag.chunkers import fixed_char_chunks, semantic_chunks
from aiops_agent.rag.k8s_loader import load_curated_k8s_docs
from aiops_agent.rag.vector_store import SimpleVectorStore, _chroma_result_to_chunks


def test_k8s_docs_have_operational_topics():
    docs = load_curated_k8s_docs()
    titles = {doc["title"] for doc in docs}

    assert "Debug Pods" in titles
    assert "Resource Management" in titles
    assert "DNS Troubleshooting" in titles


def test_k8s_docs_manifest_reaches_required_official_page_volume():
    docs = load_curated_k8s_docs()
    estimated_pages = sum(int(doc["estimated_pages"]) for doc in docs)

    assert estimated_pages >= 50
    assert len(docs) >= 10
    assert all(doc["source"].startswith("https://kubernetes.io/docs/") for doc in docs)


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
    assert all(chunk.text.count("```") in {0, 2} for chunk in chunks)


def test_fixed_char_chunks_skips_pure_overlap_tail():
    docs = [{"title": "Exact", "source": "local", "text": "abcdefghij"}]

    chunks = fixed_char_chunks(docs, chunk_size=10, overlap=2)

    assert [chunk.text for chunk in chunks] == ["abcdefghij"]


def test_fixed_char_chunks_rejects_overlap_not_smaller_than_chunk_size():
    docs = [{"title": "Bad", "source": "local", "text": "abcdef"}]

    with pytest.raises(ValueError, match="overlap must be smaller"):
        fixed_char_chunks(docs, chunk_size=4, overlap=4)


def test_simple_vector_store_tie_break_keeps_original_order():
    chunks = [
        TextChunk(chunk_id="first", title="Alpha", text="aaa", source="local"),
        TextChunk(chunk_id="second", title="Zulu", text="bbb", source="local"),
    ]
    store = SimpleVectorStore(chunks)

    retrieved = store.query("unmatched", top_k=2)

    assert [item.chunk_id for item in retrieved] == ["first", "second"]


def test_chroma_cosine_distance_conversion_is_non_negative():
    rows = _chroma_result_to_chunks(
        {
            "ids": [["chunk-1", "chunk-2"]],
            "documents": [["same direction", "opposite direction"]],
            "metadatas": [[
                {"title": "One", "source": "local"},
                {"title": "Two", "source": "local"},
            ]],
            "distances": [[0.25, 1.25]],
        }
    )

    assert [row.score for row in rows] == [0.75, 0.0]


def test_rag_eval_returns_recall_for_two_strategies():
    docs = load_curated_k8s_docs()
    rows = evaluate_chunking_strategies(docs, rag_test_queries())

    assert {row["strategy"] for row in rows} == {"fixed", "semantic"}
    assert all("recall_at_5" in row for row in rows)


def test_rag_eval_uses_paragraph_ground_truth():
    docs = load_curated_k8s_docs()
    queries = rag_test_queries()

    assert all("expected_paragraph_ids" in query for query in queries)

    rows = evaluate_chunking_strategies(docs, queries)

    assert all("avg_paragraphs_per_chunk" in row for row in rows)
    assert all(row["ground_truth_level"] == "paragraph" for row in rows)


def test_curated_docs_produce_distinct_chunking_shapes():
    docs = load_curated_k8s_docs()

    fixed = fixed_char_chunks(docs)
    semantic = semantic_chunks(docs)

    assert len(fixed) != len(semantic)
    assert all(chunk.paragraph_ids for chunk in fixed + semantic)
