import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional

import structlog

from finrag.core.config import settings

logger = structlog.get_logger(__name__)


class BaseEmbeddingProvider(ABC):
    """Abstract interface for embedding generation providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of generated embeddings."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of text inputs.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        pass

    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text input."""
        results = self.embed([text])
        return results[0]


class SentenceTransformerProvider(BaseEmbeddingProvider):
    """Embedding provider using Sentence Transformers (requires sentence-transformers package).

    Uses BAAI/bge-large-en-v1.5 by default, producing 1024-dimensional vectors.
    This provider requires the `sentence-transformers` package to be installed.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._model = None
        self._dimension = settings.EMBEDDING_DIMENSION

    def _load_model(self):
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(
                    "Loaded Sentence Transformer model",
                    model=self.model_name,
                    dimension=self._dimension,
                )
            except ImportError:
                raise ImportError(
                    "sentence-transformers package is required for SentenceTransformerProvider. "
                    "Install it with: pip install sentence-transformers"
                )

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Sentence Transformers with batching."""
        self._load_model()

        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = self._model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            all_embeddings.extend(embeddings.tolist())

        logger.debug(
            "Generated embeddings batch",
            total_texts=len(texts),
            dimension=self._dimension,
        )
        return all_embeddings


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for testing without GPU/PyTorch.

    Generates reproducible embeddings based on text content hashing.
    """

    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic mock embeddings from text hashes."""
        embeddings = []
        for text in texts:
            # Create a deterministic hash-based vector
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            # Use hash bytes to seed deterministic float values
            vector = []
            for i in range(0, min(len(text_hash) * 2, self._dimension)):
                char_idx = i % len(text_hash)
                # Convert hex character to float in range [0, 1]
                val = int(text_hash[char_idx], 16) / 15.0
                vector.append(val)

            # Pad remaining dimensions with cycling pattern
            while len(vector) < self._dimension:
                idx = len(vector) % len(text_hash)
                vector.append(int(text_hash[idx], 16) / 15.0)

            # Normalize the vector (L2 norm)
            norm = sum(v * v for v in vector) ** 0.5
            if norm > 0:
                vector = [v / norm for v in vector]

            embeddings.append(vector)

        return embeddings


def get_embedding_provider(use_mock: bool = False) -> BaseEmbeddingProvider:
    """Factory function returning the configured embedding provider.

    Args:
        use_mock: If True, returns MockEmbeddingProvider regardless of config.

    Returns:
        Configured embedding provider instance.
    """
    if use_mock:
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

    try:
        return SentenceTransformerProvider()
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. Falling back to MockEmbeddingProvider.",
            model=settings.EMBEDDING_MODEL,
        )
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
