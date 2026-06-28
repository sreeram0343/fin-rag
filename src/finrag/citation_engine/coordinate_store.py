import json
from typing import Any, Dict, Optional

import structlog

from finrag.db.chunk_repository import ChunkRepository

logger = structlog.get_logger(__name__)


class CoordinateStore:
    """Coordinate query service retrieving layout coordinates from the system database."""

    def __init__(self, chunk_repo: ChunkRepository) -> None:
        self.chunk_repo = chunk_repo

    async def get_chunk_coordinates(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Fetch coordinates, page number, and header context for a specific chunk.

        Args:
            chunk_id: Unique chunk identifier.

        Returns:
            Dictionary containing x1, y1, x2, y2 bounds, page, document_id, and section.
        """
        logger.info("Fetching coordinates for chunk", chunk_id=chunk_id)
        chunk = await self.chunk_repo.get_by_id(chunk_id)
        if not chunk:
            logger.warning("Chunk not found in database", chunk_id=chunk_id)
            return None

        # Parse coordinates list [x0, y0, x1, y1]
        bbox_raw = chunk.bounding_box
        if isinstance(bbox_raw, str):
            try:
                bbox_raw = json.loads(bbox_raw)
            except Exception:
                bbox_raw = [0.0, 0.0, 0.0, 0.0]

        if not isinstance(bbox_raw, list) or len(bbox_raw) < 4:
            logger.error("Invalid bounding box coordinate format in DB", chunk_id=chunk_id, bbox=bbox_raw)
            bbox_raw = [0.0, 0.0, 0.0, 0.0]

        return {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "page": chunk.page_number,
            "x1": float(bbox_raw[0]),
            "y1": float(bbox_raw[1]),
            "x2": float(bbox_raw[2]),
            "y2": float(bbox_raw[3]),
            "section": chunk.parent_header,
            "chunk_type": chunk.chunk_type,
        }
