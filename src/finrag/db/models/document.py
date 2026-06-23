import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from finrag.db.session import Base

class Document(Base):
    """SQLAlchemy model representing a parsed filing document."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    ticker = Column(String(5), nullable=False, index=True)
    period = Column(String(5), nullable=False)
    year = Column(Integer, nullable=False, index=True)
    storage_uri = Column(String(512), nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False)
    status = Column(String(32), nullable=False)  # QUEUED, PROCESSING, COMPLETED, FAILED
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    """SQLAlchemy model representing a chunk segment from a parsed document."""
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    bounding_box = Column(JSON, nullable=False)  # List[int] representing [x0, y0, x1, y1]
    chunk_text = Column(String, nullable=False)
    chunk_type = Column(String(16), nullable=False)  # 'TEXT' or 'TABLE'
    parent_header = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")
