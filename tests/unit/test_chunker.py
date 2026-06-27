import pytest
from finrag.chunker.base import ChunkOutput, estimate_token_count, split_text_at_sentences
from finrag.chunker.financial import FinancialChunker
from finrag.parser.base import BoundingBox, ParsedDocument, ParsedItem


def _make_item(item_type: str, text: str, page: int = 1, item_id: str = "item-1") -> ParsedItem:
    """Helper to create a ParsedItem for testing."""
    return ParsedItem(
        id=item_id,
        type=item_type,
        text=text,
        page_number=page,
        bounding_box=BoundingBox(x0=0, y0=0, x1=100, y1=100),
        metadata={},
    )


def _make_parsed_doc(items: list, doc_id: str = "doc-123") -> ParsedDocument:
    """Helper to create a ParsedDocument for testing."""
    return ParsedDocument(
        document_id=doc_id,
        ticker="AAPL",
        period="Q3",
        year=2026,
        items=items,
    )


# --- Token estimation tests ---

def test_estimate_token_count_basic() -> None:
    """Verify token estimation produces reasonable counts."""
    count = estimate_token_count("Hello world, this is a test sentence.")
    assert count > 0
    assert count < 20  # 7 words * 1.33 ≈ 9


def test_estimate_token_count_empty() -> None:
    """Verify empty string returns at least 1."""
    count = estimate_token_count("")
    assert count >= 1


# --- Sentence splitting tests ---

def test_split_text_at_sentences_within_limit() -> None:
    """Text within token limit should return a single chunk."""
    text = "Revenue was strong. Growth was stable."
    segments = split_text_at_sentences(text, max_tokens=100, overlap_tokens=10)
    assert len(segments) == 1
    assert segments[0] == text


def test_split_text_at_sentences_exceeds_limit() -> None:
    """Long text should be split into multiple segments."""
    sentences = [f"Sentence number {i} has important information." for i in range(50)]
    text = " ".join(sentences)
    segments = split_text_at_sentences(text, max_tokens=50, overlap_tokens=10)
    assert len(segments) > 1
    # Each segment should be roughly within the token budget
    for seg in segments:
        tokens = estimate_token_count(seg)
        # Allow some tolerance for the approximation
        assert tokens < 80, f"Segment too long: {tokens} tokens"


def test_split_text_at_sentences_empty() -> None:
    """Empty text should return empty list."""
    segments = split_text_at_sentences("", max_tokens=100, overlap_tokens=10)
    assert segments == []


def test_split_text_at_sentences_overlap() -> None:
    """Verify overlapping content exists between consecutive chunks."""
    sentences = [f"Sentence {i} contains data point." for i in range(30)]
    text = " ".join(sentences)
    segments = split_text_at_sentences(text, max_tokens=30, overlap_tokens=15)
    if len(segments) >= 2:
        # The end of the first segment should share some content with the start of the second
        first_words = set(segments[0].split()[-5:])
        second_words = set(segments[1].split()[:10])
        # There should be some overlap (shared words)
        assert len(first_words & second_words) > 0


# --- FinancialChunker tests ---

def test_chunker_empty_document() -> None:
    """Empty document should produce zero chunks."""
    doc = _make_parsed_doc(items=[])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)
    assert chunks == []


def test_chunker_table_never_split() -> None:
    """TABLE items should never be split, even if very long."""
    long_table_text = "| Col1 | Col2 |\n| --- | --- |\n" + "\n".join(
        [f"| Row {i} | Value {i} |" for i in range(200)]
    )
    doc = _make_parsed_doc(items=[
        _make_item("TABLE", long_table_text),
    ])
    chunker = FinancialChunker(max_chunk_tokens=10)  # Very small limit
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "TABLE"
    assert chunks[0].text == long_table_text


def test_chunker_header_propagation() -> None:
    """Headers should propagate as parent_header to subsequent items."""
    doc = _make_parsed_doc(items=[
        _make_item("HEADER", "Revenue Analysis", item_id="h1"),
        _make_item("TEXT", "Revenue grew significantly in this quarter.", item_id="t1"),
        _make_item("TABLE", "| Metric | Value |\n| --- | --- |\n| Revenue | 100B |", item_id="tb1"),
        _make_item("HEADER", "Cost Analysis", item_id="h2"),
        _make_item("TEXT", "Costs were reduced through optimization.", item_id="t2"),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    # Find chunks
    header_chunks = [c for c in chunks if c.chunk_type == "HEADER"]
    text_chunks = [c for c in chunks if c.chunk_type == "TEXT"]
    table_chunks = [c for c in chunks if c.chunk_type == "TABLE"]

    assert len(header_chunks) == 2
    assert len(table_chunks) == 1
    assert len(text_chunks) == 2

    # First text chunk should have "Revenue Analysis" as parent header
    assert text_chunks[0].parent_header == "Revenue Analysis"
    # Table should also have "Revenue Analysis" as parent header
    assert table_chunks[0].parent_header == "Revenue Analysis"
    # Second text chunk should have "Cost Analysis" as parent header
    assert text_chunks[1].parent_header == "Cost Analysis"


def test_chunker_footnote_linking() -> None:
    """Footnotes should be linked to the subsequent TABLE chunk."""
    doc = _make_parsed_doc(items=[
        _make_item("FOOTNOTE", "(1) Includes intercompany adjustments.", item_id="fn1"),
        _make_item("TABLE", "| Metric | Value |\n| --- | --- |\n| Revenue (1) | 100B |", item_id="tb1"),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    table_chunks = [c for c in chunks if c.chunk_type == "TABLE"]
    assert len(table_chunks) == 1
    assert "Footnotes:" in table_chunks[0].text
    assert "(1) Includes intercompany adjustments" in table_chunks[0].text
    assert table_chunks[0].metadata["has_footnotes"] is True
    assert table_chunks[0].metadata["footnote_count"] == 1


def test_chunker_long_text_splitting() -> None:
    """Long TEXT items should be split at sentence boundaries."""
    long_text = ". ".join([f"This is sentence number {i} with important financial data" for i in range(50)]) + "."
    doc = _make_parsed_doc(items=[
        _make_item("TEXT", long_text, item_id="t1"),
    ])
    chunker = FinancialChunker(max_chunk_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk(doc)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.chunk_type == "TEXT"
        assert chunk.document_id == "doc-123"


def test_chunker_preserves_document_id() -> None:
    """All chunks should carry the correct document_id."""
    doc = _make_parsed_doc(items=[
        _make_item("HEADER", "Summary"),
        _make_item("TEXT", "Short content here."),
    ], doc_id="custom-doc-id")
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    for chunk in chunks:
        assert chunk.document_id == "custom-doc-id"


def test_chunker_page_number_preserved() -> None:
    """Chunks should preserve the source page number."""
    doc = _make_parsed_doc(items=[
        _make_item("TEXT", "Page one content.", page=1, item_id="t1"),
        _make_item("TEXT", "Page three content.", page=3, item_id="t2"),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 3


def test_chunker_bounding_box_preserved() -> None:
    """Chunks should preserve the source bounding box."""
    doc = _make_parsed_doc(items=[
        _make_item("TEXT", "Content here."),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    assert chunks[0].bounding_box.x0 == 0
    assert chunks[0].bounding_box.y1 == 100


def test_chunker_unlinked_footnotes_become_text() -> None:
    """Footnotes not followed by a TABLE should become TEXT chunks."""
    doc = _make_parsed_doc(items=[
        _make_item("FOOTNOTE", "(1) Standalone footnote.", item_id="fn1"),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "TEXT"
    assert "(1) Standalone footnote" in chunks[0].text


def test_chunk_output_has_token_count() -> None:
    """All chunks should have a positive token_count."""
    doc = _make_parsed_doc(items=[
        _make_item("TEXT", "Revenue grew 15% year over year."),
    ])
    chunker = FinancialChunker()
    chunks = chunker.chunk(doc)

    for chunk in chunks:
        assert chunk.token_count > 0
