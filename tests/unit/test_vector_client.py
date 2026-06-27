import pytest
from qdrant_client.models import PointStruct

from finrag.db.vector.client import MockVectorClient


# --- Collection management tests ---

def test_collection_creation() -> None:
    """Verify collection is created on first use."""
    client = MockVectorClient(vector_dimension=256)
    assert client._collection_created is False
    client.ensure_collection()
    assert client._collection_created is True


def test_collection_auto_created_on_upsert() -> None:
    """Verify collection is auto-created during upsert."""
    client = MockVectorClient()
    assert client._collection_created is False
    points = [PointStruct(id="p1", vector=[0.1] * 1024, payload={})]
    client.upsert_vectors(points)
    assert client._collection_created is True


# --- Upsert tests ---

def test_upsert_single_point() -> None:
    """Verify single point upsert."""
    client = MockVectorClient(vector_dimension=128)
    points = [PointStruct(id="p1", vector=[0.5] * 128, payload={"key": "value"})]
    client.upsert_vectors(points)
    assert client.point_count == 1


def test_upsert_multiple_points() -> None:
    """Verify multiple point upsert."""
    client = MockVectorClient(vector_dimension=64)
    points = [
        PointStruct(id=f"p{i}", vector=[0.1 * i] * 64, payload={"idx": i})
        for i in range(10)
    ]
    client.upsert_vectors(points)
    assert client.point_count == 10


def test_upsert_overwrites_existing() -> None:
    """Verify upserting with same ID overwrites the existing point."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([PointStruct(id="p1", vector=[0.1] * 64, payload={"v": 1})])
    client.upsert_vectors([PointStruct(id="p1", vector=[0.2] * 64, payload={"v": 2})])
    assert client.point_count == 1

    results = client.search(query_vector=[0.1] * 64)
    assert results[0]["payload"]["v"] == 2


def test_upsert_empty_list() -> None:
    """Verify empty upsert is a no-op."""
    client = MockVectorClient()
    client.upsert_vectors([])
    assert client.point_count == 0


# --- Search tests ---

def test_search_returns_all_points() -> None:
    """Verify search without filters returns all points (up to top_k)."""
    client = MockVectorClient(vector_dimension=64)
    for i in range(5):
        client.upsert_vectors([PointStruct(id=f"p{i}", vector=[0.1] * 64, payload={"idx": i})])

    results = client.search(query_vector=[0.1] * 64, top_k=100)
    assert len(results) == 5


def test_search_respects_top_k() -> None:
    """Verify search respects the top_k limit."""
    client = MockVectorClient(vector_dimension=64)
    for i in range(10):
        client.upsert_vectors([PointStruct(id=f"p{i}", vector=[0.1] * 64, payload={})])

    results = client.search(query_vector=[0.1] * 64, top_k=3)
    assert len(results) == 3


def test_search_with_single_filter() -> None:
    """Verify search with a single metadata filter."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([
        PointStruct(id="p1", vector=[0.1] * 64, payload={"ticker": "AAPL"}),
        PointStruct(id="p2", vector=[0.2] * 64, payload={"ticker": "MSFT"}),
        PointStruct(id="p3", vector=[0.3] * 64, payload={"ticker": "AAPL"}),
    ])

    results = client.search(query_vector=[0.1] * 64, filters={"ticker": "AAPL"})
    assert len(results) == 2
    assert all(r["payload"]["ticker"] == "AAPL" for r in results)


def test_search_with_multiple_filters() -> None:
    """Verify search with multiple metadata filters (AND logic)."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([
        PointStruct(id="p1", vector=[0.1] * 64, payload={"ticker": "AAPL", "year": 2026}),
        PointStruct(id="p2", vector=[0.2] * 64, payload={"ticker": "AAPL", "year": 2025}),
        PointStruct(id="p3", vector=[0.3] * 64, payload={"ticker": "MSFT", "year": 2026}),
    ])

    results = client.search(query_vector=[0.1] * 64, filters={"ticker": "AAPL", "year": 2026})
    assert len(results) == 1
    assert results[0]["id"] == "p1"


def test_search_no_matching_filter() -> None:
    """Verify search returns empty when no points match filters."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([
        PointStruct(id="p1", vector=[0.1] * 64, payload={"ticker": "AAPL"}),
    ])

    results = client.search(query_vector=[0.1] * 64, filters={"ticker": "GOOG"})
    assert len(results) == 0


def test_search_returns_mock_score() -> None:
    """Verify search results include score field."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([PointStruct(id="p1", vector=[0.1] * 64, payload={})])

    results = client.search(query_vector=[0.1] * 64)
    assert len(results) == 1
    assert "score" in results[0]
    assert isinstance(results[0]["score"], float)


# --- Deletion tests ---

def test_delete_by_document_id() -> None:
    """Verify deletion removes only matching document's points."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([
        PointStruct(id="p1", vector=[0.1] * 64, payload={"document_id": "doc-1"}),
        PointStruct(id="p2", vector=[0.2] * 64, payload={"document_id": "doc-1"}),
        PointStruct(id="p3", vector=[0.3] * 64, payload={"document_id": "doc-2"}),
    ])
    assert client.point_count == 3

    client.delete_by_document_id("doc-1")
    assert client.point_count == 1

    results = client.search(query_vector=[0.1] * 64)
    assert results[0]["payload"]["document_id"] == "doc-2"


def test_delete_nonexistent_document() -> None:
    """Verify deletion of nonexistent document is a no-op."""
    client = MockVectorClient(vector_dimension=64)
    client.upsert_vectors([
        PointStruct(id="p1", vector=[0.1] * 64, payload={"document_id": "doc-1"}),
    ])
    client.delete_by_document_id("doc-999")
    assert client.point_count == 1


def test_delete_all_for_document() -> None:
    """Verify all points for a document are deleted."""
    client = MockVectorClient(vector_dimension=64)
    for i in range(5):
        client.upsert_vectors([
            PointStruct(id=f"p{i}", vector=[0.1] * 64, payload={"document_id": "doc-1"})
        ])
    assert client.point_count == 5

    client.delete_by_document_id("doc-1")
    assert client.point_count == 0
