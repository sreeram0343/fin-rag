from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    """Represents a 2D bounding box on a PDF page coordinate canvas."""
    x0: float = Field(..., description="Leftmost coordinate position")
    y0: float = Field(..., description="Bottommost coordinate position")
    x1: float = Field(..., description="Rightmost coordinate position")
    y1: float = Field(..., description="Topmost coordinate position")

    def to_list(self) -> List[float]:
        """Convert fields to list layout [x0, y0, x1, y1]."""
        return [self.x0, self.y0, self.x1, self.y1]

class ParsedItem(BaseModel):
    """A single segment extracted from a document (e.g., table, paragraph)."""
    id: str = Field(..., description="Unique segment identifier")
    type: Literal["TEXT", "TABLE", "HEADER", "FOOTNOTE"] = Field(..., description="Type of segment")
    text: str = Field(..., description="Raw text content of the segment")
    page_number: int = Field(..., description="1-indexed PDF page number")
    bounding_box: BoundingBox = Field(..., description="Bounding box on the page")
    parent_header: Optional[str] = Field(default=None, description="Section header containing this segment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional structured layout parameters")

from typing import Literal  # Make sure Literal is imported

class ParsedDocument(BaseModel):
    """The complete structured representation of a parsed document."""
    document_id: str = Field(..., description="Unique document ID in database")
    ticker: str = Field(..., description="Company ticker symbol")
    period: str = Field(..., description="Report period (e.g., Q1, Q2, FY)")
    year: int = Field(..., description="Fiscal year")
    items: List[ParsedItem] = Field(default_factory=list, description="Ordered list of parsed layout nodes")

class BaseParser(ABC):
    """Abstract interface class that all layout-aware document parsers must implement."""
    
    @abstractmethod
    def parse(
        self,
        file_path: str,
        document_id: str,
        ticker: str,
        period: str,
        year: int
    ) -> ParsedDocument:
        """Parse raw PDF document file path returning structured document data."""
        pass
