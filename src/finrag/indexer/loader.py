import datetime
import uuid
from typing import List, Optional

import structlog
from qdrant_client.models import PointStruct

from finrag.chunker.base import ChunkOutput
from finrag.db.chunk_repository import ChunkRepository
from finrag.db.models.document import DocumentChunk
from finrag.db.vector.client import BaseVectorClient
from finrag.indexer.embeddings import BaseEmbeddingProvider

logger = structlog.get_logger(__name__)


class VectorLoader:
    """Orchestrates embedding generation and vector database loading for document chunks.

    Coordinates:
    1. Generating embeddings from chunk text via an embedding provider
    2. Upserting vectors with metadata payloads into the vector database
    3. Persisting DocumentChunk records to PostgreSQL
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        vector_client: BaseVectorClient,
        chunk_repo: Optional[ChunkRepository] = None,
        batch_size: int = 32,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_client = vector_client
        self.chunk_repo = chunk_repo
        self.batch_size = batch_size

    async def load_chunks(self, chunks: List[ChunkOutput]) -> int:
        """Generate embeddings and load chunks into vector DB and PostgreSQL.

        Args:
            chunks: List of ChunkOutput items to index.

        Returns:
            Number of successfully indexed chunks.
        """
        if not chunks:
            logger.warning("No chunks provided to VectorLoader")
            return 0

        document_id = chunks[0].document_id
        logger.info(
            "Starting vector loading pipeline",
            document_id=document_id,
            total_chunks=len(chunks),
        )

        # 1. Generate embeddings in batches
        texts = [chunk.text for chunk in chunks]
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            batch_embeddings = self.embedding_provider.embed(batch_texts)
            all_embeddings.extend(batch_embeddings)
            logger.debug(
                "Generated embeddings batch",
                batch_start=i,
                batch_size=len(batch_texts),
            )

        # 1.5 Retrieve document metadata for metadata preservation in Qdrant
        ticker = "UNKNOWN"
        fiscal_period = "UNKNOWN"
        document_type = "10-Q"
        document_path = ""
        if self.chunk_repo:
            from finrag.db.models.document import Document
            from sqlalchemy.future import select
            stmt = select(Document).where(Document.id == document_id)
            res = await self.chunk_repo.session.execute(stmt)
            doc = res.scalars().first()
            if doc:
                ticker = doc.ticker
                fiscal_period = f"{doc.period} {doc.year}"
                document_path = doc.storage_uri
                document_type = "10-K" if doc.period == "FY" else "10-Q"

        # 2. Build Qdrant point structs with metadata payloads
        points: List[PointStruct] = []
        for chunk, embedding in zip(chunks, all_embeddings):
            meta = chunk.metadata or {}
            paragraph_id = meta.get("block_index")
            table_id = meta.get("table_index")

            point = PointStruct(
                id=chunk.chunk_id,
                vector=embedding,
                payload={
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "chunk_type": chunk.chunk_type,
                    "page_number": chunk.page_number,
                    "parent_header": chunk.parent_header,
                    "token_count": chunk.token_count,
                    "text": chunk.text,
                    # Add bounding box as flat values for Qdrant payload
                    "bbox_x0": chunk.bounding_box.x0,
                    "bbox_y0": chunk.bounding_box.y0,
                    "bbox_x1": chunk.bounding_box.x1,
                    "bbox_y1": chunk.bounding_box.y1,
                    # Normalized bbox coordinate objects
                    "bbox": {
                        "x1": chunk.bounding_box.x0,
                        "y1": chunk.bounding_box.y0,
                        "x2": chunk.bounding_box.x1,
                        "y2": chunk.bounding_box.y1,
                    },
                    "section": chunk.parent_header,
                    "ticker": ticker,
                    "period": fiscal_period,
                    "fiscal_period": fiscal_period,
                    "document_type": document_type,
                    "document_path": document_path,
                    "paragraph_id": paragraph_id,
                    "table_id": table_id,
                    "paragraph": chunk.text if chunk.chunk_type == "TEXT" else None,
                    "table": chunk.text if chunk.chunk_type == "TABLE" else None,
                    "figure": None,
                },
            )
            points.append(point)

        # 3. Upsert into vector database
        self.vector_client.upsert_vectors(points, batch_size=self.batch_size)
        logger.info(
            "Upserted vectors to database",
            document_id=document_id,
            points_count=len(points),
        )

        # 4. Persist DocumentChunk records to PostgreSQL (if repo provided)
        if self.chunk_repo:
            db_chunks = self._build_db_chunks(chunks)
            await self.chunk_repo.save_bulk(db_chunks)
            logger.info(
                "Persisted chunks to PostgreSQL",
                document_id=document_id,
                chunk_count=len(db_chunks),
            )

        return len(chunks)

    @staticmethod
    def _build_db_chunks(chunks: List[ChunkOutput]) -> List[DocumentChunk]:
        """Convert ChunkOutput items to SQLAlchemy DocumentChunk models."""
        db_chunks = []
        for chunk in chunks:
            db_chunk = DocumentChunk(
                id=chunk.chunk_id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                bounding_box=chunk.bounding_box.to_list(),
                chunk_text=chunk.text,
                chunk_type=chunk.chunk_type,
                parent_header=chunk.parent_header,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db_chunks.append(db_chunk)
        return db_chunks
