import io
from typing import Any, Dict, List

import structlog
from fpdf import FPDF

logger = structlog.get_logger(__name__)


def clean_pdf_text(text: str) -> str:
    """Sanitize input string by converting unicode markers to latin-1 safe characters."""
    replacements = {
        "\u201c": '"',  # Left smart quote
        "\u201d": '"',  # Right smart quote
        "\u2018": "'",  # Left single quote
        "\u2019": "'",  # Right single quote
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2713": "Check",  # Checkmark
        "\u2714": "Check",
        "\u2022": "*",  # Bullet point
    }
    for unicode_char, latin_char in replacements.items():
        text = text.replace(unicode_char, latin_char)
    # Filter out anything not representable in latin1 encoding
    return text.encode("latin-1", errors="ignore").decode("latin-1")


class PDFReport(FPDF):
    """Custom FPDF class managing header and footer layout templates."""

    def header(self) -> None:
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "FinRAG Institutional Research Platform | Factual Synthesis", 0, 0, "L")
        self.set_draw_color(220, 220, 220)
        self.line(10, 18, 200, 18)
        self.ln(12)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        # Display page index dynamically
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", 0, 0, "C")


def compile_pdf_report(
    answer: str,
    citations: List[Dict[str, Any]],
    title: str = "Financial Research Report",
) -> bytes:
    """Compile generated report summary text and coordinate citations into a PDF report.

    Args:
        answer: Synthesized RAG report summary text.
        citations: List of coordinate citation dictionaries.
        title: Target title header of the PDF report.

    Returns:
        Compiled PDF document bytes.
    """
    logger.info("Compiling PDF document report", title=title, citations_count=len(citations))

    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Document Header Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(31, 73, 125)  # Corporate Navy Blue
    pdf.cell(0, 10, clean_pdf_text(title), 0, 1, "L")
    pdf.ln(5)

    # Render body paragraphs
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(51, 51, 51)  # Dark Gray

    # Clean body text
    cleaned_answer = clean_pdf_text(answer)
    pdf.multi_cell(0, 5, cleaned_answer)
    pdf.ln(10)

    # Citation coordinates index appendix page
    if citations:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(31, 73, 125)
        pdf.cell(0, 10, "Source Citations Appendix", 0, 1, "L")
        pdf.set_draw_color(220, 220, 220)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        # Header Columns
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(31, 73, 125)
        pdf.set_text_color(255, 255, 255)

        col_widths = [12, 70, 15, 43, 50]  # Total matches text margins (190mm)
        headers = ["Ref", "Document ID", "Page", "Section Scope", "Coordinates BBox"]

        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, 1, 0, "C", True)
        pdf.ln()

        # Rows mappings
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 51, 51)

        for idx, cit in enumerate(citations, start=1):
            doc_id = clean_pdf_text(str(cit.get("document_id", "Unknown")))
            page_num = str(cit.get("page", ""))
            section = clean_pdf_text(cit.get("section") or "MD&A Section")
            bbox = cit.get("bbox") or {}
            x1, y1, x2, y2 = bbox.get("x1", 0), bbox.get("y1", 0), bbox.get("x2", 0), bbox.get("y2", 0)
            bbox_str = f"({int(x1)},{int(y1)})-({int(x2)},{int(y2)})"

            pdf.cell(col_widths[0], 8, f"[{idx}]", 1, 0, "C")
            pdf.cell(col_widths[1], 8, doc_id[:40], 1, 0, "L")
            pdf.cell(col_widths[2], 8, page_num, 1, 0, "C")
            pdf.cell(col_widths[3], 8, section[:25], 1, 0, "L")
            pdf.cell(col_widths[4], 8, bbox_str, 1, 0, "C")
            pdf.ln()

    # Compile bytes
    pdf_bytes = pdf.output()
    logger.info("Compiled PDF document successfully", size=len(pdf_bytes))
    return bytes(pdf_bytes)
