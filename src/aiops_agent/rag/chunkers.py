from __future__ import annotations

from dataclasses import dataclass
import re

from aiops_agent.models.schemas import TextChunk


@dataclass(frozen=True)
class _ParagraphBlock:
    text: str
    paragraph_id: str
    start: int
    end: int


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
        blocks = _paragraph_blocks(doc, doc_index)
        step = chunk_size - overlap
        emitted_until = 0
        chunk_index = 0
        for start in range(0, len(text), step):
            end = min(start + chunk_size, len(text))
            # 最后一段如果完全落在上一段 overlap 内，就不会增加新内容，直接跳过。
            if end <= emitted_until:
                continue

            piece = text[start:end].strip()
            if not piece:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=f"fixed-{doc_index}-{chunk_index}",
                    title=doc["title"],
                    text=piece,
                    source=doc["source"],
                    paragraph_ids=_overlapping_paragraph_ids(blocks, start, end),
                )
            )
            emitted_until = end
            chunk_index += 1
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
        blocks = _paragraph_blocks(doc, doc_index)
        current = ""
        current_ids: tuple[str, ...] = ()
        chunk_index = 0

        for block in blocks:
            candidate = f"{current}\n\n{block.text}".strip() if current else block.text
            candidate_ids = current_ids + (block.paragraph_id,)
            if current and len(candidate) > target_size:
                chunks.append(
                    _build_chunk(
                        doc,
                        doc_index,
                        chunk_index,
                        current,
                        "semantic",
                        current_ids,
                    )
                )
                chunk_index += 1
                current = _join_overlap(current, block.text, overlap)
                current_ids = (block.paragraph_id,)
                continue
            current = candidate
            current_ids = candidate_ids

        if current.strip():
            chunks.append(
                _build_chunk(
                    doc,
                    doc_index,
                    chunk_index,
                    current,
                    "semantic",
                    current_ids,
                )
            )

    return chunks


def _build_chunk(
    doc: dict[str, str],
    doc_index: int,
    chunk_index: int,
    text: str,
    strategy: str,
    paragraph_ids: tuple[str, ...],
) -> TextChunk:
    return TextChunk(
        chunk_id=f"{strategy}-{doc_index}-{chunk_index}",
        title=doc["title"],
        text=text.strip(),
        source=doc["source"],
        paragraph_ids=paragraph_ids,
    )


def _paragraph_blocks(doc: dict[str, str], doc_index: int) -> list[_ParagraphBlock]:
    text = doc["text"].strip()
    raw_blocks = _split_preserving_code_blocks(text)
    blocks: list[_ParagraphBlock] = []
    cursor = 0

    for block_index, block in enumerate(raw_blocks):
        start = text.find(block, cursor)
        if start < 0:
            start = cursor
        end = start + len(block)
        blocks.append(
            _ParagraphBlock(
                text=block,
                paragraph_id=f"{doc['title']}#p{block_index}",
                start=start,
                end=end,
            )
        )
        cursor = end

    return blocks


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


def _overlapping_paragraph_ids(
    blocks: list[_ParagraphBlock],
    start: int,
    end: int,
) -> tuple[str, ...]:
    return tuple(
        block.paragraph_id
        for block in blocks
        if block.start < end and block.end > start
    )


def _validate_chunk_args(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk size")
