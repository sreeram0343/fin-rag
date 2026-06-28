import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from finrag.main import app
from finrag.api.dependencies import get_orchestrator
from finrag.core.security import create_access_token


# 1. Setup Mock Orchestrator dependency override
mock_orchestrator = MagicMock()
mock_orchestrator.ask = AsyncMock(return_value={
    "answer": "Calculated value is 40%.",
    "citations": [{"text": "value is 40%", "document_id": "doc123", "page": 1, "bounding_box": [0,0,10,10]}]
})
mock_orchestrator.compare = AsyncMock(return_value={
    "source_document_id": "src-uuid",
    "target_document_id": "tgt-uuid",
    "semantic_changes": [{"type": "ADDED", "summary": "Added cybersecurity section."}],
    "lexical_diff": "<p>Diff HTML</p>"
})

app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator


@pytest.fixture
def auth_header() -> dict:
    """Provide a valid mock JWT authorization header with query scopes."""
    token = create_access_token(
        data={"sub": "test_user", "scopes": ["read:queries"]}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unauthorized_header() -> dict:
    """Provide a JWT token lacking queries read scopes."""
    token = create_access_token(
        data={"sub": "test_user", "scopes": ["read:documents"]}
    )
    return {"Authorization": f"Bearer {token}"}


# --- QA Ask API Tests ---

def test_ask_unauthorized(client: TestClient) -> None:
    """Verify ask query endpoint fails when token is not provided."""
    response = client.post(
        "/api/v1/queries/ask",
        json={"query": "What is the margin?", "ticker": "AAPL"}
    )
    assert response.status_code == 401


def test_ask_insufficient_permissions(client: TestClient, unauthorized_header: dict) -> None:
    """Verify ask query endpoint fails when token lacks read:queries scope."""
    response = client.post(
        "/api/v1/queries/ask",
        headers=unauthorized_header,
        json={"query": "What is the margin?", "ticker": "AAPL"}
    )
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


def test_ask_success(client: TestClient, auth_header: dict) -> None:
    """Verify successful ask query return."""
    response = client.post(
        "/api/v1/queries/ask",
        headers=auth_header,
        json={"query": "What is the margin?", "ticker": "AAPL", "filters": {"years": [2026]}}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert "answer" in json_data
    assert len(json_data["citations"]) == 1
    assert json_data["citations"][0]["document_id"] == "doc123"
    mock_orchestrator.ask.assert_called_once()


def test_ask_invalid_query_length(client: TestClient, auth_header: dict) -> None:
    """Verify query length validations."""
    response = client.post(
        "/api/v1/queries/ask",
        headers=auth_header,
        json={"query": "abc", "ticker": "AAPL"}  # Under 5 chars
    )
    assert response.status_code == 422


def test_ask_invalid_ticker(client: TestClient, auth_header: dict) -> None:
    """Verify ticker validations."""
    response = client.post(
        "/api/v1/queries/ask",
        headers=auth_header,
        json={"query": "What is the margin?", "ticker": "INVALIDTICKER"}
    )
    assert response.status_code == 422


# --- Comparative API Tests ---

def test_compare_success(client: TestClient, auth_header: dict) -> None:
    """Verify successful comparative query return."""
    src_id = str(uuid.uuid4())
    tgt_id = str(uuid.uuid4())

    response = client.post(
        "/api/v1/queries/compare",
        headers=auth_header,
        json={
            "ticker": "TSLA",
            "source_document_id": src_id,
            "target_document_id": tgt_id,
            "sections": ["risk_factors"]
        }
    )
    assert response.status_code == 200
    json_data = response.json()
    assert "semantic_changes" in json_data
    assert len(json_data["semantic_changes"]) == 1
    assert json_data["semantic_changes"][0]["type"] == "ADDED"
    mock_orchestrator.compare.assert_called_once()


def test_compare_invalid_uuids(client: TestClient, auth_header: dict) -> None:
    """Verify UUID fields validations."""
    response = client.post(
        "/api/v1/queries/compare",
        headers=auth_header,
        json={
            "ticker": "TSLA",
            "source_document_id": "invalid-uuid-1",
            "target_document_id": "invalid-uuid-2"
        }
    )
    assert response.status_code == 422
    assert "UUID" in response.json()["detail"][0]["msg"]
