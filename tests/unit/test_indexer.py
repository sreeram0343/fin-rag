import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from finrag.chunker.base import ChunkOutput
from finrag.db.vector.client import MockVectorClient
from finrag.indexer.embeddings import MockEmbeddingProvider
from finrag.indexer.loader import VectorLoader
from finrag.parser.base import BoundingBox


def _make_chunk(chunk_id: str = "chunk-1", text: str = "Revenue grew 15%", doc_id: str = "doc-1") -> ChunkOutput:
    """Helper to create a ChunkOutput for testing."""
    return ChunkOutput(
        chunk_id=chunk_id,
        document_id=doc_id,
        text=text,
        chunk_type="TEXT",
        page_number=1,
        bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=100),
        parent_header="Revenue Analysis",
        token_count=10,
        metadata={},
    )


# --- MockEmbeddingProvider tests ---

def test_mock_embedding_dimension() -> None:
    """Verify mock provider returns correct dimensions."""
    provider = MockEmbeddingProvider(dimension=1024)
    assert provider.dimension == 1024


def test_mock_embedding_returns_correct_count() -> None:
    """Verify mock provider returns one embedding per input text."""
    provider = MockEmbeddingProvider(dimension=256)
    texts = ["Hello world", "Test embedding", "Third text"]
    embeddings = provider.embed(texts)
    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 256


def test_mock_embedding_deterministic() -> None:
    """Verify same text produces same embedding."""
    provider = MockEmbeddingProvider(dimension=128)
    emb1 = provider.embed(["Hello world"])[0]
    emb2 = provider.embed(["Hello world"])[0]
    assert emb1 == emb2


def test_mock_embedding_different_texts() -> None:
    """Verify different texts produce different embeddings."""
    provider = MockEmbeddingProvider(dimension=128)
    emb1 = provider.embed(["Hello world"])[0]
    emb2 = provider.embed(["Goodbye world"])[0]
    assert emb1 != emb2


def test_mock_embedding_normalized() -> None:
    """Verify mock embeddings are approximately L2-normalized."""
    provider = MockEmbeddingProvider(dimension=256)
    embedding = provider.embed(["Test text"])[0]
    norm = sum(v * v for v in embedding) ** 0.5
    assert abs(norm - 1.0) < 0.01  # Should be close to 1.0


def test_mock_embedding_single() -> None:
    """Verify embed_single convenience method."""
    provider = MockEmbeddingProvider(dimension=128)
    embedding = provider.embed_single("Hello")
    assert len(embedding) == 128


# --- MockVectorClient tests ---

def test_mock_vector_client_upsert_and_search() -> None:
    """Verify mock client stores and returns points."""
    from qdrant_client.models import PointStruct

    client = MockVectorClient(vector_dimension=128)
    points = [
        PointStruct(id="p1", vector=[0.1] * 128, payload={"document_id": "doc-1", "text": "Revenue"}),
        PointStruct(id="p2", vector=[0.2] * 128, payload={"document_id": "doc-1", "text": "Costs"}),
    ]
    client.upsert_vectors(points)
    assert client.point_count == 2

    results = client.search(query_vector=[0.1] * 128, top_k=10)
    assert len(results) == 2


def test_mock_vector_client_filtered_search() -> None:
    """Verify mock client filters by metadata."""
    from qdrant_client.models import PointStruct

    client = MockVectorClient()
    points = [
        PointStruct(id="p1", vector=[0.1] * 1024, payload={"document_id": "doc-1"}),
        PointStruct(id="p2", vector=[0.2] * 1024, payload={"document_id": "doc-2"}),
    ]
    client.upsert_vectors(points)

    results = client.search(query_vector=[0.1] * 1024, filters={"document_id": "doc-1"})
    assert len(results) == 1
    assert results[0]["payload"]["document_id"] == "doc-1"


def test_mock_vector_client_delete() -> None:
    """Verify mock client deletes by document_id."""
    from qdrant_client.models import PointStruct

    client = MockVectorClient()
    points = [
        PointStruct(id="p1", vector=[0.1] * 1024, payload={"document_id": "doc-1"}),
        PointStruct(id="p2", vector=[0.2] * 1024, payload={"document_id": "doc-2"}),
    ]
    client.upsert_vectors(points)
    assert client.point_count == 2

    client.delete_by_document_id("doc-1")
    assert client.point_count == 1


# --- VectorLoader tests ---

@pytest.mark.asyncio
async def test_vector_loader_empty_chunks() -> None:
    """Verify loader handles empty chunk list gracefully."""
    provider = MockEmbeddingProvider(dimension=128)
    client = MockVectorClient(vector_dimension=128)
    loader = VectorLoader(embedding_provider=provider, vector_client=client)
    result = await loader.load_chunks([])
    assert result == 0


@pytest.mark.asyncio
async def test_vector_loader_loads_chunks() -> None:
    """Verify loader generates embeddings and upserts vectors."""
    provider = MockEmbeddingProvider(dimension=128)
    client = MockVectorClient(vector_dimension=128)
    loader = VectorLoader(embedding_provider=provider, vector_client=client, batch_size=2)

    chunks = [
        _make_chunk(chunk_id=f"c{i}", text=f"Chunk text number {i}", doc_id="doc-1")
        for i in range(5)
    ]
    result = await loader.load_chunks(chunks)

    assert result == 5
    assert client.point_count == 5


@pytest.mark.asyncio
async def test_vector_loader_payload_metadata() -> None:
    """Verify upserted vectors contain correct payload metadata."""
    provider = MockEmbeddingProvider(dimension=128)
    client = MockVectorClient(vector_dimension=128)
    loader = VectorLoader(embedding_provider=provider, vector_client=client)

    chunks = [_make_chunk(chunk_id="c1", text="Revenue data", doc_id="doc-42")]
    await loader.load_chunks(chunks)

    results = client.search(query_vector=[0.1] * 128)
    assert len(results) == 1
    payload = results[0]["payload"]
    assert payload["document_id"] == "doc-42"
    assert payload["chunk_id"] == "c1"
    assert payload["chunk_type"] == "TEXT"
    assert payload["parent_header"] == "Revenue Analysis"


@pytest.mark.asyncio
async def test_vector_loader_builds_db_chunks() -> None:
    """Verify _build_db_chunks creates correct DocumentChunk models."""
    chunks = [
        _make_chunk(chunk_id="c1", text="Revenue data", doc_id="doc-1"),
        _make_chunk(chunk_id="c2", text="Cost data", doc_id="doc-1"),
    ]
    db_chunks = VectorLoader._build_db_chunks(chunks)

    assert len(db_chunks) == 2
    assert db_chunks[0].id == "c1"
    assert db_chunks[0].document_id == "doc-1"
    assert db_chunks[0].chunk_text == "Revenue data"
    assert db_chunks[0].chunk_type == "TEXT"
    assert db_chunks[0].parent_header == "Revenue Analysis"
    assert db_chunks[0].bounding_box == [0, 0, 100, 100]


@pytest.mark.asyncio
async def test_vector_loader_batch_size_handling() -> None:
    """Verify loader respects batch size for embedding generation."""
    call_count = 0
    original_embed = MockEmbeddingProvider.embed

    class CountingProvider(MockEmbeddingProvider):
        def embed(self, texts):
            nonlocal call_count
            call_count += 1
            return super().embed(texts)

    provider = CountingProvider(dimension=128)
    client = MockVectorClient(vector_dimension=128)
    loader = VectorLoader(embedding_provider=provider, vector_client=client, batch_size=3)

    chunks = [
        _make_chunk(chunk_id=f"c{i}", text=f"Text {i}", doc_id="doc-1")
        for i in range(7)
    ]
    await loader.load_chunks(chunks)

    # 7 chunks with batch_size=3 should produce 3 embedding batches (3+3+1)
    assert call_count == 3
