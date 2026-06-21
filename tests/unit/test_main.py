import uuid
from fastapi.testclient import TestClient
from finrag.main import app
from finrag.core.exceptions import ValidationException

def test_health_check(client: TestClient) -> None:
    """Verify the health check endpoint returns 200 and structural status."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"
    assert "project" in json_data

def test_correlation_id_tracing_passed(client: TestClient) -> None:
    """Verify that an incoming Correlation ID header is echoed back."""
    test_cid = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Correlation-ID": test_cid})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == test_cid

def test_correlation_id_tracing_generated(client: TestClient) -> None:
    """Verify that if no Correlation ID is passed, one is generated and returned."""
    response = client.get("/health")
    assert response.status_code == 200
    generated_cid = response.headers.get("X-Correlation-ID")
    assert generated_cid is not None
    # Verify it matches UUID structure
    assert uuid.UUID(generated_cid)

def test_custom_api_exception_handling(client: TestClient) -> None:
    """Verify custom ApiExceptions translate to structured responses."""
    # Temporarily register a test endpoint that throws ValidationException
    @app.get("/_test_validation_error")
    def trigger_error() -> None:
        raise ValidationException("Field checks failed", details=[{"field": "test", "issue": "failed"}])
    
    response = client.get("/_test_validation_error")
    assert response.status_code == 422
    json_data = response.json()
    assert "error" in json_data
    err = json_data["error"]
    assert err["code"] == "VALIDATION_FAILED"
    assert err["message"] == "Field checks failed"
    assert err["details"] == [{"field": "test", "issue": "failed"}]
    assert "correlation_id" in err
