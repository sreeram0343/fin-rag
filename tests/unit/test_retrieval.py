import pytest
from unittest.mock import AsyncMock, MagicMock

from finrag.db.models.document import Document, DocumentChunk
from finrag.db.vector.client import MockVectorClient
from finrag.indexer.embeddings import MockEmbeddingProvider
from finrag.retriever.hybrid import BM25, HybridRetriever
from finrag.retriever.reranker import CrossEncoderReranker


def test_bm25_tokenization_and_scoring() -> None:
    """Verify BM25 tokenization splits words correctly and scoring ranks matching docs higher."""
    corpus = [
        {"id": "doc1", "text": "Operating revenues rose to fifty billion dollars."},
        {"id": "doc2", "text": "Lease liabilities for next year were not disclosed."},
    ]

    bm25 = BM25(corpus)
    assert bm25.num_docs == 2
    assert "revenues" in bm25.idf

    scores_rev = bm25.score("operating revenues")
    assert scores_rev[0] > scores_rev[1]

    scores_lease = bm25.score("lease liabilities")
    assert scores_lease[1] > scores_rev[1]


@pytest.mark.asyncio
async def test_hybrid_retriever_filtering_and_rrf() -> None:
    """Verify retriever filters files correctly and fuses dense/sparse ranks."""
    # Setup mocks
    doc_repo = MagicMock()
    chunk_repo = MagicMock()

    doc1 = Document(id="d1", ticker="AAPL", period="Q3", year=2026, status="COMPLETED")
    doc2 = Document(id="d2", ticker="AAPL", period="Q1", year=2025, status="COMPLETED")
    doc_repo.list_all = AsyncMock(return_value=[doc1, doc2])

    chunk1 = DocumentChunk(
        id="c1",
        document_id="d1",
        page_number=1,
        bounding_box=[10, 20, 30, 40],
        chunk_text="Operating margin calculation info.",
        chunk_type="TEXT",
        parent_header="Guidance",
    )
    chunk2 = DocumentChunk(
        id="c2",
        document_id="d2",
        page_number=2,
        bounding_box=[15, 25, 35, 45],
        chunk_text="Lease liabilities table data.",
        chunk_type="TABLE",
        parent_header="Leases Note",
    )

    # Repository returns chunks based on doc_id
    def mock_get_chunks(doc_id):
        if doc_id == "d1":
            return [chunk1]
        elif doc_id == "d2":
            return [chunk2]
        return []

    chunk_repo.get_by_document_id = AsyncMock(side_effect=mock_get_chunks)

    # Mock Vector Client & Embeddings
    vector_client = MockVectorClient(vector_dimension=128)
    # Register point in vector DB to match search
    from qdrant_client.models import PointStruct
    vector_client.upsert_vectors([
        PointStruct(id="c1", vector=[0.1] * 128, payload={"document_id": "d1", "ticker": "AAPL"}),
        PointStruct(id="c2", vector=[0.2] * 128, payload={"document_id": "d2", "ticker": "AAPL"}),
    ])

    embedder = MockEmbeddingProvider(dimension=128)

    # Hybrid Retriever with no reranker
    retriever = HybridRetriever(
        vector_client=vector_client,
        embedding_provider=embedder,
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
    )

    # Query with year filter restricting to 2026
    results = await retriever.retrieve(
        query="operating margin",
        ticker="AAPL",
        filters={"years": [2026]},
    )

    # Should only return chunk1 from d1 (2026)
    assert len(results) == 1
    assert results[0]["id"] == "c1"
    assert results[0]["chunk_text"] == "Operating margin calculation info."
    assert results[0]["page_number"] == 1


def test_cross_encoder_reranker_fallback() -> None:
    """Verify CrossEncoderReranker falls back gracefully to token overlap scoring."""
    reranker = CrossEncoderReranker()
    # Force fallback mode
    reranker._is_fallback = True

    candidates = [
        {"id": "c1", "chunk_text": "Income rose by five percent."},
        {"id": "c2", "chunk_text": "Lease commitments detailed in table."},
    ]

    results = reranker.rerank(query="lease commitments", candidates=candidates, top_k=2)
    assert len(results) == 2
    # c2 must rank first because it matches 'lease' and 'commitments'
    assert results[0]["id"] == "c2"
    assert results[0]["score"] > results[1]["score"]
