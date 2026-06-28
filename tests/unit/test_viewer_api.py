import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
import io

from finrag.main import app
from finrag.core.security import create_access_token


@pytest.fixture
def auth_header() -> dict:
    """Provide a valid mock JWT authorization header with documents read scopes."""
    token = create_access_token(
        data={"sub": "test_user", "scopes": ["read:documents"]}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unauthorized_header() -> dict:
    """Provide a JWT token lacking read:documents scope."""
    token = create_access_token(
        data={"sub": "test_user", "scopes": ["read:queries"]}
    )
    return {"Authorization": f"Bearer {token}"}


# --- Viewer API Tests ---

@patch("finrag.api.v1.viewer._resolve_local_pdf")
@patch("finrag.api.v1.viewer.get_pdf_page_count")
@patch("finrag.api.v1.viewer._renderer.render_page")
def test_get_page_image_success(
    mock_render: MagicMock,
    mock_page_count: MagicMock,
    mock_resolve: MagicMock,
    client: TestClient,
    auth_header: dict,
) -> None:
    """Verify document page rendering endpoints returns PNG images."""
    mock_resolve.return_value = "/local/path/doc.pdf"
    mock_page_count.return_value = 10
    
    # Create simple PNG bytes to return
    img = Image.new("RGB", (100, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mock_render.return_value = buf.getvalue()

    response = client.get(
        "/api/v1/documents/doc-1111-2222/page/3",
        headers=auth_header
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0
    mock_render.assert_called_once_with("/local/path/doc.pdf", 3, 150)


@patch("finrag.api.v1.viewer._resolve_local_pdf")
@patch("finrag.api.v1.viewer.get_pdf_page_count")
@patch("finrag.api.v1.viewer._renderer.render_page")
def test_get_page_out_of_bounds(
    mock_render: MagicMock,
    mock_page_count: MagicMock,
    mock_resolve: MagicMock,
    client: TestClient,
    auth_header: dict,
) -> None:
    """Verify page requests out of bounds return HTTP 400 Bad Request."""
    mock_resolve.return_value = "/local/path/doc.pdf"
    mock_page_count.return_value = 10

    response = client.get(
        "/api/v1/documents/doc-1111-2222/page/22",  # 22 > 10 pages
        headers=auth_header
    )
    assert response.status_code == 400
    assert "out of range" in response.json()["detail"]


@patch("finrag.api.v1.viewer._resolve_local_pdf")
@patch("finrag.api.v1.viewer.get_pdf_page_count")
@patch("finrag.api.v1.viewer._renderer.render_page")
@patch("finrag.api.v1.viewer.highlight_coordinate_region")
def test_get_highlight_success(
    mock_highlight: MagicMock,
    mock_render: MagicMock,
    mock_page_count: MagicMock,
    mock_resolve: MagicMock,
    client: TestClient,
    auth_header: dict,
) -> None:
    """Verify highlight endpoint renders overlay boxes correctly."""
    mock_resolve.return_value = "/local/path/doc.pdf"
    mock_page_count.return_value = 5
    
    img = Image.new("RGB", (100, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    
    mock_render.return_value = buf.getvalue()
    mock_highlight.return_value = b"highlighted-bytes-png"

    response = client.get(
        "/api/v1/documents/doc-1111-2222/highlight?page=2&x1=100&y1=200&x2=300&y2=400",
        headers=auth_header
    )
    assert response.status_code == 200
    assert response.content == b"highlighted-bytes-png"
    mock_highlight.assert_called_once_with(
        buf.getvalue(),
        {"x1": 100.0, "y1": 200.0, "x2": 300.0, "y2": 400.0}
    )


def test_get_highlight_invalid_coordinates(client: TestClient, auth_header: dict) -> None:
    """Verify highlight parameters validation constraints."""
    response = client.get(
        "/api/v1/documents/doc-1111-2222/highlight?page=2&x1=-50&y1=200&x2=300&y2=1200",  # x1 < 0, y2 > 1000
        headers=auth_header
    )
    assert response.status_code == 422


def test_viewer_insufficient_permissions(client: TestClient, unauthorized_header: dict) -> None:
    """Verify RBAC scope verification."""
    response = client.get(
        "/api/v1/documents/doc-1111-2222/page/1",
        headers=unauthorized_header
    )
    assert response.status_code == 403
