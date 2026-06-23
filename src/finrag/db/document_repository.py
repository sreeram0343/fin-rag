from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from finrag.db.base import BaseRepository
from finrag.db.models.document import Document

class DocumentRepository(BaseRepository[Document]):
    """Repository handling database access for Document entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: str) -> Optional[Document]:
        """Fetch a document by its unique UUID ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == entity_id)
        )
        return result.scalars().first()

    async def save(self, entity: Document) -> Document:
        """Persist a new or modified document into the database."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_hash(self, file_hash: str) -> Optional[Document]:
        """Retrieve a document by its unique file SHA-256 hash."""
        result = await self.session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalars().first()

    async def list_all(self, ticker: Optional[str] = None) -> List[Document]:
        """List all documents, optionally filtered by company ticker."""
        stmt = select(Document)
        if ticker:
            stmt = stmt.where(Document.ticker == ticker)
        stmt = stmt.order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
