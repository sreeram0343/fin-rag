from typing import List, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from finrag.db.base import BaseRepository
from finrag.db.models.document import DocumentChunk


class ChunkRepository(BaseRepository[DocumentChunk]):
    """Repository handling database access for DocumentChunk entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: str) -> Optional[DocumentChunk]:
        """Fetch a single chunk by its unique ID."""
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.id == entity_id)
        )
        return result.scalars().first()

    async def save(self, entity: DocumentChunk) -> DocumentChunk:
        """Persist a single chunk record."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def save_bulk(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Batch insert multiple chunk records efficiently."""
        if not chunks:
            return []
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def get_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        """Retrieve all chunks belonging to a specific document."""
        result = await self.session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_number, DocumentChunk.id)
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a document. Returns the number of deleted rows."""
        result = await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self.session.flush()
        return result.rowcount

    async def count_by_document_id(self, document_id: str) -> int:
        """Count chunks belonging to a specific document."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )
        return result.scalar() or 0
