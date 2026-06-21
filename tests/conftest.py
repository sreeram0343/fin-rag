import pytest
from fastapi.testclient import TestClient
from finrag.main import app

@pytest.fixture(scope="session")
def client() -> TestClient:
    """Fixture providing a synchronized TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c
