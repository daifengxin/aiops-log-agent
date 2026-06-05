from __future__ import annotations

import re
from collections import Counter
from math import sqrt
from pathlib import Path
from typing import Any

from aiops_agent.models.schemas import RetrievedChunk, TextChunk

CHROMA_COLLECTION_METADATA = {"hnsw:space": "cosine"}
_PARAGRAPH_ID_SEPARATOR = "\x1f"


class ChromaVectorStore:
    """ChromaDB 主检索路径；重依赖只在实例化时加载。"""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "k8s_docs",
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 单元测试只用 SimpleVectorStore，避免 import 模块时下载或加载 embedding 模型。
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            collection_name,
            metadata=CHROMA_COLLECTION_METADATA,
        )

    def rebuild(self, chunks: list[TextChunk]) -> None:
        if self.collection.count():
            existing = self.collection.get()
            ids = existing.get("ids", [])
            if ids:
                self.collection.delete(ids=ids)

        if not chunks:
            return

        embeddings = self.model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
        ).tolist()
        self.collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "title": chunk.title,
                    "source": chunk.source,
                    "paragraph_ids": _pack_paragraph_ids(chunk.paragraph_ids),
                }
                for chunk in chunks
            ],
            embeddings=embeddings,
        )

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        embedding = self.model.encode([query_text], normalize_embeddings=True).tolist()[0]
        result = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        return _chroma_result_to_chunks(result)


class SimpleVectorStore:
    """轻量词法余弦检索器，用于离线单元测试和 RAG 召回评估。"""

    def __init__(self, chunks: list[TextChunk]) -> None:
        self.chunks = chunks
        # 标题参与向量化，避免短查询只命中正文偶然词而忽略主题。
        self.vectors = [_vectorize(f"{chunk.title} {chunk.text}") for chunk in chunks]

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        query_vector = _vectorize(query_text)
        scored: list[tuple[float, int, TextChunk]] = []
        for index, (chunk, vector) in enumerate(zip(self.chunks, self.vectors, strict=True)):
            scored.append((_cosine(query_vector, vector), index, chunk))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                text=chunk.text,
                source=chunk.source,
                score=round(score, 4),
                paragraph_ids=chunk.paragraph_ids,
            )
            for score, _, chunk in scored[:top_k]
        ]


def _chroma_result_to_chunks(result: dict[str, Any]) -> list[RetrievedChunk]:
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    rows: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
        strict=True,
    ):
        # Chroma collection 使用 cosine space；distance 越小越相似，分数裁剪到非负便于展示。
        score = max(0.0, 1.0 - float(distance))
        rows.append(
            RetrievedChunk(
                chunk_id=str(chunk_id),
                title=str(metadata["title"]),
                text=str(text),
                source=str(metadata["source"]),
                score=round(score, 4),
                paragraph_ids=_unpack_paragraph_ids(
                    str(metadata.get("paragraph_ids", ""))
                ),
            )
        )
    return rows


def _pack_paragraph_ids(paragraph_ids: tuple[str, ...]) -> str:
    return _PARAGRAPH_ID_SEPARATOR.join(paragraph_ids)


def _unpack_paragraph_ids(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item for item in value.split(_PARAGRAPH_ID_SEPARATOR) if item)


def _vectorize(text: str) -> Counter[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return Counter(tokens)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0

    common = set(left) & set(right)
    dot = sum(left[word] * right[word] for word in common)
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
