import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from finrag.core.config import settings

logger = structlog.get_logger(__name__)


class BaseVectorClient(ABC):
    """Abstract interface for vector database operations."""

    @abstractmethod
    def ensure_collection(self) -> None:
        """Create the vector collection if it doesn't exist."""
        pass

    @abstractmethod
    def upsert_vectors(self, points: List[PointStruct], batch_size: int = 64) -> None:
        """Batch upsert vector points into the collection."""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute vector similarity search with optional metadata filters."""
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> None:
        """Delete all vectors belonging to a specific document."""
        pass


class QdrantVectorClient(BaseVectorClient):
    """Production Qdrant vector database client."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        vector_dimension: Optional[int] = None,
    ) -> None:
        self.url = url or settings.VECTOR_DB_URL
        self.api_key = api_key or settings.VECTOR_DB_API_KEY.get_secret_value()
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.vector_dimension = vector_dimension or settings.EMBEDDING_DIMENSION

        # Initialize Qdrant client
        if self.api_key and self.api_key != "mock-vector-db-api-key":
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
        else:
            self.client = QdrantClient(url=self.url)

        logger.info(
            "Initialized Qdrant vector client",
            url=self.url,
            collection=self.collection_name,
            dimension=self.vector_dimension,
        )

    def ensure_collection(self) -> None:
        """Create the finrag_chunks collection if it doesn't already exist."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            logger.info(
                "Qdrant collection already exists",
                collection=self.collection_name,
                points_count=collection_info.points_count,
            )
        except (UnexpectedResponse, Exception):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "Created new Qdrant collection",
                collection=self.collection_name,
                dimension=self.vector_dimension,
                distance="COSINE",
            )

    def upsert_vectors(self, points: List[PointStruct], batch_size: int = 64) -> None:
        """Batch upsert vector points into the Qdrant collection."""
        if not points:
            return

        self.ensure_collection()

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            logger.debug(
                "Upserted vector batch",
                batch_start=i,
                batch_size=len(batch),
                total=len(points),
            )

        logger.info(
            "Completed vector upsert",
            collection=self.collection_name,
            total_points=len(points),
        )

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute vector similarity search with optional metadata filtering."""
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            qdrant_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in results
        ]

    def delete_by_document_id(self, document_id: str) -> None:
        """Delete all vectors belonging to a specific document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(
            "Deleted vectors for document",
            collection=self.collection_name,
            document_id=document_id,
        )


class MockVectorClient(BaseVectorClient):
    """In-memory mock vector client for testing and development without Qdrant."""

    def __init__(self, vector_dimension: int = 1024) -> None:
        self.vector_dimension = vector_dimension
        self.collection_name = "mock_collection"
        self._points: Dict[str, Dict[str, Any]] = {}
        self._collection_created = False

    def ensure_collection(self) -> None:
        """Mark collection as created."""
        self._collection_created = True

    def upsert_vectors(self, points: List[PointStruct], batch_size: int = 64) -> None:
        """Store points in memory."""
        self.ensure_collection()
        for point in points:
            self._points[str(point.id)] = {
                "id": str(point.id),
                "vector": point.vector,
                "payload": point.payload or {},
            }

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return all stored points (no actual similarity computation in mock)."""
        results = []
        for point_data in self._points.values():
            payload = point_data["payload"]

            # Apply filters if provided
            if filters:
                match = all(payload.get(k) == v for k, v in filters.items())
                if not match:
                    continue

            results.append(
                {
                    "id": point_data["id"],
                    "score": 0.95,  # Mock score
                    "payload": payload,
                }
            )

        return results[:top_k]

    def delete_by_document_id(self, document_id: str) -> None:
        """Remove all points matching the document_id."""
        to_delete = [
            pid
            for pid, data in self._points.items()
            if data["payload"].get("document_id") == document_id
        ]
        for pid in to_delete:
            del self._points[pid]

    @property
    def point_count(self) -> int:
        """Return the number of stored points."""
        return len(self._points)
