"""Text chunker for splitting documents into token-sized chunks."""

import logging
from typing import Any

import tiktoken

from alphawatch.agents.state import Chunk
from alphawatch.config import get_settings

logger = logging.getLogger(__name__)

# Use cl100k_base (GPT-4 / Titan compatible tokenizer)
_ENCODING_NAME = "cl100k_base"


def get_tokenizer() -> tiktoken.Encoding:
    """Return the shared tiktoken tokenizer.

    Returns:
        The cl100k_base tokenizer instance.
    """
    return tiktoken.get_encoding(_ENCODING_NAME)


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split text into token-sized chunks with overlap.

    Uses tiktoken cl100k_base tokenizer for accurate token counting.
    Chunks are split on token boundaries.

    Args:
        text: The full document text to chunk.
        chunk_size: Maximum tokens per chunk. Defaults to config value (512).
        chunk_overlap: Overlap tokens between chunks. Defaults to config value (64).
        metadata: Base metadata to attach to each chunk.

    Returns:
        List of Chunk objects with sequential chunk_index values.
    """
    settings = get_settings()
    size = chunk_size or settings.chunk_size_tokens
    overlap = chunk_overlap or settings.chunk_overlap_tokens
    base_meta = metadata or {}

    enc = get_tokenizer()
    tokens = enc.encode(text)

    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = enc.decode(chunk_tokens)

        chunks.append(
            Chunk(
                content=chunk_text_str,
                chunk_index=idx,
                metadata={**base_meta, "token_count": len(chunk_tokens)},
            )
        )

        idx += 1
        start += size - overlap

        # Avoid infinite loop if overlap >= size
        if size - overlap <= 0:
            break

    logger.debug(
        "Chunked %d tokens into %d chunks (size=%d, overlap=%d)",
        len(tokens), len(chunks), size, overlap,
    )
    return chunks
