import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import io

from finrag.citation_engine.coordinate_store import CoordinateStore
from finrag.citation_engine.highlighter import highlight_coordinate_region
from finrag.citation_engine.mapper import resolve_citations
from finrag.citation_engine.pdf_renderer import get_pdf_page_count, render_pdf_page_to_bytes
from finrag.db.models.document import DocumentChunk


def test_highlighter_pillow_overlay() -> None:
    """Verify highlighter draws outline over normalized bounds successfully."""
    # 1. Create a dummy transparent 100x100 PNG image
    img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # 2. Apply coordinates highlight overlay
    bbox = {"x1": 100, "y1": 200, "x2": 900, "y2": 800}
    highlighted_bytes = highlight_coordinate_region(img_bytes, bbox)

    # 3. Verify it output a valid image
    res_img = Image.open(io.BytesIO(highlighted_bytes))
    assert res_img.size == (100, 100)


@pytest.mark.asyncio
async def test_coordinate_store_db_lookup() -> None:
    """Verify coordinate store queries DB record and formats coordinates."""
    chunk_repo = MagicMock()
    chunk = DocumentChunk(
        id="chunk_id_123",
        document_id="doc_abc",
        page_number=5,
        bounding_box=[100, 200, 900, 800],
        chunk_text="Filing revenue footnote data.",
        chunk_type="TEXT",
        parent_header="MD&A Summary",
    )
    chunk_repo.get_by_id = AsyncMock(return_value=chunk)

    store = CoordinateStore(chunk_repo)
    res = await store.get_chunk_coordinates("chunk_id_123")

    assert res is not None
    assert res["page"] == 5
    assert res["x1"] == 100.0
    assert res["y2"] == 800.0
    assert res["section"] == "MD&A Summary"


def test_resolve_citations_mapping() -> None:
    """Verify mapper resolves inline bracket tags and checks math status."""
    candidates = [
        {
            "id": "c1",
            "document_id": "d1",
            "page_number": 12,
            "bounding_box": [50, 100, 150, 200],
            "parent_header": "Income note",
            "score": 0.95,
            "chunk_text": "Revenues rose to 120 million.",
        }
    ]

    # LLM text containing citation tag [Chunk 1]
    response = "Company revenues reached a record level [Chunk 1]."
    citations = resolve_citations(response, candidates, verified_math_vars={"result": 120.0})

    assert len(citations) == 1
    assert citations[0]["chunk_id"] == "c1"
    assert citations[0]["page"] == 12
    # Verify math overlap flag triggers verification badge
    assert citations[0]["confidence"]["verification_status"] == "verified"
    assert citations[0]["bbox"] == {"x1": 50.0, "y1": 100.0, "x2": 150.0, "y2": 200.0}


@patch("pdfplumber.open")
def test_pdf_renderer_page_extraction(mock_open: MagicMock) -> None:
    """Verify PDF rendering calls pdfplumber routines."""
    mock_page = MagicMock()
    mock_display_img = MagicMock()
    mock_display_img.original = Image.new("RGB", (200, 300))
    mock_page.to_image.return_value = mock_display_img

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_open.return_value.__enter__.return_value = mock_pdf

    res_bytes = render_pdf_page_to_bytes("dummy.pdf", 1)
    assert len(res_bytes) > 0
    mock_open.assert_called_once_with("dummy.pdf")
