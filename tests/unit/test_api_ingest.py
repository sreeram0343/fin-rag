import pytest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from finrag.main import app
from finrag.db.session import Base, get_db_session
from finrag.api.dependencies import get_storage
from finrag.core.security import create_access_token
from finrag.db.models.document import Document

# 1. Setup in-memory SQLite engine for API testing
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def override_get_db_session():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

app.dependency_overrides[get_db_session] = override_get_db_session

# 2. Mock storage client
mock_storage = AsyncMock()
mock_storage.upload_file.return_value = "file:///mock/storage/path.pdf"
mock_storage.download_file.return_value = b"Mock PDF Content"
app.dependency_overrides[get_storage] = lambda: mock_storage

@pytest.fixture(autouse=True, scope="module")
async def init_db():
    """Create in-memory SQLite tables for the module tests, then teardown."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(autouse=True)
async def clear_db():
    """Clear database records between test runs."""
    async with test_session_factory() as session:
        async with session.begin():
            from sqlalchemy import delete
            await session.execute(delete(Document))
    yield

@pytest.fixture
def mock_celery():
    """Mock Celery task scheduler."""
    with patch("finrag.api.v1.ingest.process_document_task.apply_async") as mock_apply:
        yield mock_apply

@pytest.fixture
def auth_header() -> dict:
    """Provide a valid mock JWT authorization header."""
    token = create_access_token(
        data={"sub": "test_user", "scopes": ["read:documents", "write:documents", "read:queries"]}
    )
    return {"Authorization": f"Bearer {token}"}

# --- Test Authentication Router ---

def test_auth_token_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "client_credentials", "client_id": "user123", "client_secret": "pass123"}
    )
    assert response.status_code == 200
    json_data = response.json()
    assert "access_token" in json_data
    assert json_data["token_type"] == "bearer"
    assert "read:documents" in json_data["scope"]

def test_auth_token_invalid_grant_type(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "invalid", "client_id": "user123", "client_secret": "pass123"}
    )
    assert response.status_code == 400
    assert "Unsupported grant type" in response.json()["detail"]

# --- Test Ingestion Uploads Endpoint ---

def test_upload_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        data={"ticker": "AAPL", "period": "Q3", "year": 2026},
        files={"file": ("test.pdf", b"pdf_data", "application/pdf")}
    )
    assert response.status_code == 401

def test_upload_success(client: TestClient, auth_header: dict, mock_celery: patch) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q3", "year": 2026},
        files={"file": ("apple_10q.pdf", b"mock_pdf_binary_content", "application/pdf")}
    )
    assert response.status_code == 202
    json_data = response.json()
    assert json_data["ticker"] == "AAPL"
    assert json_data["period"] == "Q3"
    assert json_data["year"] == 2026
    assert json_data["status"] == "QUEUED"
    assert "job_id" in json_data
    assert "document_id" in json_data
    mock_celery.assert_called_once()

def test_upload_invalid_ticker(client: TestClient, auth_header: dict) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL123", "period": "Q3", "year": 2026},
        files={"file": ("apple_10q.pdf", b"mock_pdf_content", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Ticker must contain 1-5 capital alphanumeric characters" in response.json()["detail"]

def test_upload_invalid_period(client: TestClient, auth_header: dict) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q5", "year": 2026},
        files={"file": ("apple_10q.pdf", b"mock_pdf_content", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Period must match Q1-Q4" in response.json()["detail"]

def test_upload_invalid_year(client: TestClient, auth_header: dict) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q3", "year": 1850},
        files={"file": ("apple_10q.pdf", b"mock_pdf_content", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Year must fall in range" in response.json()["detail"]

def test_upload_invalid_extension(client: TestClient, auth_header: dict) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q3", "year": 2026},
        files={"file": ("apple_10q.exe", b"executable_data", "application/octet-stream")}
    )
    assert response.status_code == 400
    assert "Only PDF, HTML, or TXT files are allowed" in response.json()["detail"]

def test_upload_payload_too_large(client: TestClient, auth_header: dict) -> None:
    large_bytes = b"0" * (151 * 1024 * 1024)  # 151MB
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q3", "year": 2026},
        files={"file": ("apple_10q.pdf", large_bytes, "application/pdf")}
    )
    assert response.status_code == 413
    assert "exceeds maximum size of 150MB" in response.json()["detail"]

def test_upload_deduplication(client: TestClient, auth_header: dict, mock_celery: patch) -> None:
    payload = {"ticker": "AAPL", "period": "Q3", "year": 2026}
    file_spec = {"file": ("apple_10q.pdf", b"unique_file_content_hash", "application/pdf")}
    
    # First upload
    response1 = client.post("/api/v1/documents", headers=auth_header, data=payload, files=file_spec)
    assert response1.status_code == 202
    id1 = response1.json()["document_id"]
    
    # Second upload with identical content
    response2 = client.post("/api/v1/documents", headers=auth_header, data=payload, files=file_spec)
    assert response2.status_code == 202
    id2 = response2.json()["document_id"]
    
    assert id1 == id2  # Should return the exact same document ID (idempotent)
    assert mock_celery.call_count == 1  # Celery task should only be scheduled once!

# --- Test Job Status Polling Endpoint ---

def test_get_job_status_success(client: TestClient, auth_header: dict, mock_celery: patch) -> None:
    # 1. Create a queued job
    response = client.post(
        "/api/v1/documents",
        headers=auth_header,
        data={"ticker": "AAPL", "period": "Q3", "year": 2026},
        files={"file": ("apple_10q.pdf", b"some_unique_content_xyz", "application/pdf")}
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # 2. Poll job status
    status_response = client.get(f"/api/v1/documents/jobs/{job_id}", headers=auth_header)
    assert status_response.status_code == 200
    json_data = status_response.json()
    assert json_data["job_id"] == job_id
    assert json_data["status"] == "QUEUED"
    assert json_data["current_step"] == "QUEUED"
    assert json_data["progress_percentage"] == 10

def test_get_job_status_not_found(client: TestClient, auth_header: dict) -> None:
    non_existent_uuid = str(uuid.uuid4())
    response = client.get(f"/api/v1/documents/jobs/{non_existent_uuid}", headers=auth_header)
    assert response.status_code == 404
    assert "Job identifier does not exist" in response.json()["detail"]

def test_get_job_status_invalid_uuid(client: TestClient, auth_header: dict) -> None:
    response = client.get("/api/v1/documents/jobs/invalid-uuid-string", headers=auth_header)
    assert response.status_code == 422
    assert "Job ID must be a valid 36-character UUID" in response.json()["detail"]
