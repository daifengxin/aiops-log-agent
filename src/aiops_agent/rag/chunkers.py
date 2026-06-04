from __future__ import annotations

import re

from aiops_agent.models.schemas import TextChunk


def fixed_char_chunks(
    docs: list[dict[str, str]],
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[TextChunk]:
    """按固定字符窗口切分文档，用作 RAG 评测基线。"""

    _validate_chunk_args(chunk_size, overlap)
    chunks: list[TextChunk] = []
    for doc_index, doc in enumerate(docs):
        text = doc["text"].strip()
        step = chunk_size - overlap
        for chunk_index, start in enumerate(range(0, len(text), step)):
            piece = text[start : start + chunk_size].strip()
            if not piece:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=f"fixed-{doc_index}-{chunk_index}",
                    title=doc["title"],
                    text=piece,
                    source=doc["source"],
                )
            )
    return chunks


def semantic_chunks(
    docs: list[dict[str, str]],
    target_size: int = 900,
    overlap: int = 150,
) -> list[TextChunk]:
    """按段落语义切分，并把 fenced code block 作为不可拆分单元。"""

    _validate_chunk_args(target_size, overlap)
    chunks: list[TextChunk] = []
    for doc_index, doc in enumerate(docs):
        blocks = _split_preserving_code_blocks(doc["text"])
        current = ""
        chunk_index = 0

        for block in blocks:
            candidate = f"{current}\n\n{block}".strip() if current else block
            if current and len(candidate) > target_size:
                chunks.append(_build_chunk(doc, doc_index, chunk_index, current, "semantic"))
                chunk_index += 1
                current = _join_overlap(current, block, overlap)
                continue
            current = candidate

        if current.strip():
            chunks.append(_build_chunk(doc, doc_index, chunk_index, current, "semantic"))

    return chunks


def _build_chunk(
    doc: dict[str, str],
    doc_index: int,
    chunk_index: int,
    text: str,
    strategy: str,
) -> TextChunk:
    return TextChunk(
        chunk_id=f"{strategy}-{doc_index}-{chunk_index}",
        title=doc["title"],
        text=text.strip(),
        source=doc["source"],
    )


def _split_preserving_code_blocks(text: str) -> list[str]:
    parts = re.split(r"(```.*?```)", text.strip(), flags=re.DOTALL)
    blocks: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            blocks.append(stripped)
            continue
        blocks.extend(
            block.strip()
            for block in re.split(r"\n\s*\n", stripped)
            if block.strip()
        )
    return blocks


def _join_overlap(previous: str, block: str, overlap: int) -> str:
    if overlap <= 0:
        return block

    # overlap 只取普通文本尾部；如果上一块含代码围栏，避免截断后产生半个 code block。
    if "```" in previous:
        return block

    return f"{previous[-overlap:].strip()}\n\n{block}".strip()


def _validate_chunk_args(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk size")
