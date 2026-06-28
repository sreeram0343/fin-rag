from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseRetriever(ABC):
    """Abstract base class for all retrieval engines in the FinRAG platform."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        ticker: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks matching the query, ticker, and metadata filters.

        Args:
            query: The user query string.
            ticker: The target company ticker (e.g. "AAPL").
            filters: Optional dict of filtering conditions (e.g., years, document types).
            top_k: Number of retrieved results to return.

        Returns:
            A list of dicts containing chunk metadata, content, and scores.
        """
        pass
