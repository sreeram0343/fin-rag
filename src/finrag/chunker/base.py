import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from finrag.parser.base import BoundingBox, ParsedDocument


class ChunkOutput(BaseModel):
    """A single embeddable chunk produced by the chunking pipeline."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document UUID")
    text: str = Field(..., description="Chunk text content ready for embedding")
    chunk_type: str = Field(..., description="TEXT, TABLE, or HEADER")
    page_number: int = Field(..., description="Source PDF page number (1-indexed)")
    bounding_box: BoundingBox = Field(..., description="Source coordinates on the page")
    parent_header: Optional[str] = Field(default=None, description="Nearest preceding section header")
    token_count: int = Field(default=0, description="Approximate token count of chunk text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional structured metadata")


class BaseChunker(ABC):
    """Abstract interface for document chunking strategies."""

    @abstractmethod
    def chunk(self, parsed_doc: ParsedDocument) -> List[ChunkOutput]:
        """Split a parsed document into embeddable chunks.

        Args:
            parsed_doc: Structured output from a layout-aware document parser.

        Returns:
            Ordered list of ChunkOutput items ready for embedding generation.
        """
        pass


def estimate_token_count(text: str) -> int:
    """Estimate token count using a simple whitespace + punctuation heuristic.

    This avoids requiring tiktoken/transformers for a rough count.
    Approximation: ~0.75 words per token for English text.
    """
    words = re.findall(r"\S+", text)
    return max(1, int(len(words) * 1.33))


def split_text_at_sentences(text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
    """Split text into segments at sentence boundaries respecting token limits.

    Args:
        text: Full text content to split.
        max_tokens: Maximum token budget per chunk.
        overlap_tokens: Number of tokens to overlap between consecutive chunks.

    Returns:
        List of text segments, each within the token budget.
    """
    # Split at sentence boundaries (period, question mark, exclamation mark followed by space or newline)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return [text] if text.strip() else []

    chunks: List[str] = []
    current_sentences: List[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = estimate_token_count(sentence)

        # If a single sentence exceeds the limit, it becomes its own chunk
        if sentence_tokens > max_tokens:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0
            chunks.append(sentence)
            continue

        if current_tokens + sentence_tokens > max_tokens and current_sentences:
            chunks.append(" ".join(current_sentences))

            # Calculate overlap: keep trailing sentences that fit within overlap budget
            overlap_sentences: List[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = estimate_token_count(s)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sentences + [sentence]
            current_tokens = overlap_count + sentence_tokens
        else:
            current_sentences.append(sentence)
            current_tokens += sentence_tokens

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks
