from typing import Literal, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized coordinates representing an element's bounding box [0, 1000]."""

    x1: float = Field(..., description="Top-left horizontal coordinate")
    y1: float = Field(..., description="Top-left vertical coordinate")
    x2: float = Field(..., description="Bottom-right horizontal coordinate")
    y2: float = Field(..., description="Bottom-right vertical coordinate")


class CitationConfidence(BaseModel):
    """Confidence and audit metrics of a retrieved fact citation."""

    similarity_score: float = Field(..., description="Dense embedding retrieval cosine similarity score")
    reranker_score: Optional[float] = Field(None, description="Cross-encoder reranking score")
    verification_status: Literal["verified", "unverified"] = Field(
        "unverified",
        description="Factual verification state from mathematical sandbox auditor"
    )


class CitationObject(BaseModel):
    """Pixel-level coordinate citation mapping text assertions to document layout sections."""

    chunk_id: str = Field(..., description="Source document chunk identifier")
    document_id: str = Field(..., description="Unique document ID context")
    page: int = Field(..., description="1-based page index")
    bbox: BoundingBox = Field(..., description="Normalized bounding-box coordinates")
    section: Optional[str] = Field(None, description="Document section header context")
    ticker: str = Field(..., description="Target filing ticker symbol")
    period: str = Field(..., description="Filing fiscal period or quarter")
    confidence: CitationConfidence = Field(..., description="Relevance and auditing confidence metrics")
