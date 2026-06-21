from unittest.mock import MagicMock, patch
import pytest
from finrag.core.exceptions import PipelineException
from finrag.parser.base import BoundingBox
from finrag.parser.pdf_layout import PDFLayoutParser
from finrag.parser.utils import clean_whitespace, is_overlapping, normalize_bbox

def test_normalize_bbox() -> None:
    """Verify raw coordinate float positions scale correctly to integer grid."""
    bbox = [10.0, 20.0, 90.0, 180.0]
    normalized = normalize_bbox(bbox, page_width=100.0, page_height=200.0)
    
    # 10.0 / 100.0 * 1000 = 100
    assert normalized.x0 == 100.0
    # 20.0 / 200.0 * 1000 = 100
    assert normalized.y0 == 100.0
    # 90.0 / 100.0 * 1000 = 900
    assert normalized.x1 == 900.0
    # 180.0 / 200.0 * 1000 = 900
    assert normalized.y1 == 900.0

def test_clean_whitespace() -> None:
    """Verify consecutive whitespace and tab sequences format correctly."""
    text = "  Revenue   exceeded\t\texpectations. \n\n  Next line.  "
    cleaned = clean_whitespace(text)
    assert cleaned == "Revenue exceeded expectations.\nNext line."

def test_is_overlapping() -> None:
    """Verify overlap intersection calculations on bounding box coordinates."""
    box_a = BoundingBox(x0=10, y0=10, x1=50, y1=50)
    box_b = BoundingBox(x0=40, y0=40, x1=80, y1=80)
    box_c = BoundingBox(x0=60, y0=60, x1=90, y1=90)
    
    assert is_overlapping(box_a, box_b) is True
    assert is_overlapping(box_a, box_c) is False

def test_parser_file_not_found() -> None:
    """Verify parser fails immediately if file does not exist."""
    parser = PDFLayoutParser()
    with pytest.raises(PipelineException) as exc:
        parser.parse("nonexistent_file.pdf", "doc_123", "MOCK", "Q1", 2026)
    assert exc.value.error_code == "FILE_NOT_FOUND"

def test_pdf_parsing_layout_logic() -> None:
    """Verify layout extraction, table filtering, and block grouping using mock pdfplumber."""
    mock_page = MagicMock()
    mock_page.width = 100
    mock_page.height = 200
    
    # Define a visual table
    mock_table = MagicMock()
    mock_table.bbox = [10.0, 20.0, 50.0, 60.0]
    mock_table.extract.return_value = [
        ["Segment", "Revenue"],
        ["Cloud", "1200"]
    ]
    mock_page.find_tables.return_value = [mock_table]
    
    # Define text words (one inside table, others outside forming a paragraph)
    mock_page.extract_words.return_value = [
        # Inside table region (10 to 50, 20 to 60)
        {"x0": 15.0, "top": 25.0, "x1": 35.0, "bottom": 35.0, "text": "Segment"},
        # Outside table region
        {"x0": 10.0, "top": 80.0, "x1": 40.0, "bottom": 90.0, "text": "Operating"},
        {"x0": 45.0, "top": 80.0, "x1": 80.0, "bottom": 90.0, "text": "Income"},
    ]
    
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    
    with patch("pdfplumber.open") as mock_open, patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = mock_pdf
        
        parser = PDFLayoutParser()
        doc = parser.parse("mock.pdf", "doc_123", "AAPL", "Q2", 2026)
        
        assert doc.document_id == "doc_123"
        assert doc.ticker == "AAPL"
        assert doc.period == "Q2"
        assert doc.year == 2026
        
        # We expect 2 items: 1 Table and 1 Text block (since the inside word was filtered out)
        assert len(doc.items) == 2
        
        # Verify first item (Table)
        table_item = doc.items[0]
        assert table_item.type == "TABLE"
        assert "| Segment | Revenue |" in table_item.text
        assert "| Cloud | 1200 |" in table_item.text
        assert table_item.metadata["rows_count"] == 2
        
        # Verify second item (Text block)
        text_item = doc.items[1]
        assert text_item.type == "HEADER" or text_item.type == "TEXT"
        assert "Operating Income" in text_item.text
        assert text_item.metadata["block_index"] == 0
