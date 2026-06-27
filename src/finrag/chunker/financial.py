import uuid
from typing import List, Optional

import structlog

from finrag.chunker.base import BaseChunker, ChunkOutput, estimate_token_count, split_text_at_sentences
from finrag.parser.base import BoundingBox, ParsedDocument, ParsedItem

logger = structlog.get_logger(__name__)


class FinancialChunker(BaseChunker):
    """Financial document chunker preserving table coherence and header context.

    Key rules:
    - TABLE items are never split across chunks (table coherence).
    - HEADER items propagate as `parent_header` to subsequent TEXT/TABLE chunks.
    - FOOTNOTE items are linked to the most recent TABLE chunk if footnote markers match.
    - Long TEXT blocks are split at sentence boundaries with configurable overlap.
    """

    def __init__(self, max_chunk_tokens: int = 512, overlap_tokens: int = 64) -> None:
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, parsed_doc: ParsedDocument) -> List[ChunkOutput]:
        """Split parsed document items into embeddable chunks."""
        if not parsed_doc.items:
            logger.warning("Parsed document has no items to chunk", document_id=parsed_doc.document_id)
            return []

        chunks: List[ChunkOutput] = []
        current_header: Optional[str] = None
        pending_footnotes: List[ParsedItem] = []

        for item in parsed_doc.items:
            if item.type == "HEADER":
                current_header = item.text
                # Headers also become their own small chunks for retrieval
                chunks.append(
                    ChunkOutput(
                        chunk_id=str(uuid.uuid4()),
                        document_id=parsed_doc.document_id,
                        text=item.text,
                        chunk_type="HEADER",
                        page_number=item.page_number,
                        bounding_box=item.bounding_box,
                        parent_header=current_header,
                        token_count=estimate_token_count(item.text),
                        metadata=item.metadata,
                    )
                )

            elif item.type == "TABLE":
                # Tables are NEVER split — they become a single chunk regardless of size
                table_text = item.text

                # Link any pending footnotes to this table
                footnote_texts = self._collect_footnotes(pending_footnotes)
                if footnote_texts:
                    table_text = table_text + "\n\nFootnotes:\n" + "\n".join(footnote_texts)
                    pending_footnotes.clear()

                chunks.append(
                    ChunkOutput(
                        chunk_id=str(uuid.uuid4()),
                        document_id=parsed_doc.document_id,
                        text=table_text,
                        chunk_type="TABLE",
                        page_number=item.page_number,
                        bounding_box=item.bounding_box,
                        parent_header=current_header,
                        token_count=estimate_token_count(table_text),
                        metadata={
                            **item.metadata,
                            "has_footnotes": bool(footnote_texts),
                            "footnote_count": len(footnote_texts),
                        },
                    )
                )

            elif item.type == "FOOTNOTE":
                # Buffer footnotes to link to the next TABLE chunk
                pending_footnotes.append(item)

            elif item.type == "TEXT":
                text_tokens = estimate_token_count(item.text)

                if text_tokens <= self.max_chunk_tokens:
                    # Small enough to be a single chunk
                    chunks.append(
                        ChunkOutput(
                            chunk_id=str(uuid.uuid4()),
                            document_id=parsed_doc.document_id,
                            text=item.text,
                            chunk_type="TEXT",
                            page_number=item.page_number,
                            bounding_box=item.bounding_box,
                            parent_header=current_header,
                            token_count=text_tokens,
                            metadata=item.metadata,
                        )
                    )
                else:
                    # Split long text at sentence boundaries
                    text_segments = split_text_at_sentences(
                        item.text, self.max_chunk_tokens, self.overlap_tokens
                    )
                    for seg_idx, segment in enumerate(text_segments):
                        chunks.append(
                            ChunkOutput(
                                chunk_id=str(uuid.uuid4()),
                                document_id=parsed_doc.document_id,
                                text=segment,
                                chunk_type="TEXT",
                                page_number=item.page_number,
                                bounding_box=item.bounding_box,
                                parent_header=current_header,
                                token_count=estimate_token_count(segment),
                                metadata={
                                    **item.metadata,
                                    "segment_index": seg_idx,
                                    "total_segments": len(text_segments),
                                },
                            )
                        )

        # Handle any remaining footnotes that weren't linked to a table
        for fn in pending_footnotes:
            chunks.append(
                ChunkOutput(
                    chunk_id=str(uuid.uuid4()),
                    document_id=parsed_doc.document_id,
                    text=fn.text,
                    chunk_type="TEXT",
                    page_number=fn.page_number,
                    bounding_box=fn.bounding_box,
                    parent_header=current_header,
                    token_count=estimate_token_count(fn.text),
                    metadata=fn.metadata,
                )
            )

        logger.info(
            "Document chunking completed",
            document_id=parsed_doc.document_id,
            total_chunks=len(chunks),
            table_chunks=sum(1 for c in chunks if c.chunk_type == "TABLE"),
            text_chunks=sum(1 for c in chunks if c.chunk_type == "TEXT"),
            header_chunks=sum(1 for c in chunks if c.chunk_type == "HEADER"),
        )

        return chunks

    @staticmethod
    def _collect_footnotes(footnotes: List[ParsedItem]) -> List[str]:
        """Format footnote items into attribution lines."""
        return [fn.text for fn in footnotes if fn.text.strip()]
