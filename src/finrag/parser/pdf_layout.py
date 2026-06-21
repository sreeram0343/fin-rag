import os
import uuid
from typing import List, Dict, Any, Optional
import pdfplumber
import structlog
from finrag.core.exceptions import PipelineException
from finrag.parser.base import BaseParser, ParsedDocument, ParsedItem, BoundingBox
from finrag.parser.utils import normalize_bbox, clean_whitespace

logger = structlog.get_logger(__name__)

class PDFLayoutParser(BaseParser):
    """Layout-aware PDF parser separating grid tables from body paragraphs."""

    def parse(
        self,
        file_path: str,
        document_id: str,
        ticker: str,
        period: str,
        year: int
    ) -> ParsedDocument:
        """Execute visual and structural parsing over the PDF file."""
        if not os.path.exists(file_path):
            raise PipelineException(
                f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND"
            )

        logger.info(
            "Starting PDF visual parsing",
            file_path=file_path,
            ticker=ticker,
            document_id=document_id
        )

        parsed_items: List[ParsedItem] = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_number = page_idx + 1
                    page_width = float(page.width)
                    page_height = float(page.height)

                    # 1. Extract and map tables first
                    tables = page.find_tables()
                    table_bboxes: List[BoundingBox] = []

                    for table_idx, table in enumerate(tables):
                        # table.bbox format is [x0, y0, x1, y1] (top-left origin)
                        raw_bbox = list(table.bbox)
                        normalized_bbox = normalize_bbox(raw_bbox, page_width, page_height)
                        table_bboxes.append(normalized_bbox)

                        # Extract cell grid text
                        grid_data = table.extract()
                        if not grid_data:
                            continue

                        # Convert table grid to clean Markdown structure
                        markdown_rows = []
                        for row in grid_data:
                            # Filter None cells and clean whitespace
                            clean_row = [clean_whitespace(cell or "") for cell in row]
                            markdown_rows.append("| " + " | ".join(clean_row) + " |")

                        table_text = ""
                        if markdown_rows:
                            # Add headers separators if at least one row exists
                            headers_sep = "| " + " | ".join("---" for _ in grid_data[0]) + " |"
                            markdown_rows.insert(1, headers_sep)
                            table_text = "\n".join(markdown_rows)

                        # Parse footnotes mapping metadata if any footnote lines appear below table
                        parsed_items.append(
                            ParsedItem(
                                id=str(uuid.uuid4()),
                                type="TABLE",
                                text=table_text,
                                page_number=page_number,
                                bounding_box=normalized_bbox,
                                metadata={
                                    "table_index": table_idx,
                                    "columns_count": len(grid_data[0]) if grid_data else 0,
                                    "rows_count": len(grid_data)
                                }
                            )
                        )

                    # 2. Extract and filter text words
                    # We want to skip text words that are inside any table's bounding box
                    words = page.extract_words()
                    non_table_words = []

                    for w in words:
                        # w is a dict containing x0, top, x1, bottom, text
                        word_x0 = float(w["x0"])
                        word_y0 = float(w["top"])
                        word_x1 = float(w["x1"])
                        word_y1 = float(w["bottom"])

                        is_inside_table = False
                        for t_box in table_bboxes:
                            # Map normalized coordinates back to page size for checking or use raw coords
                            # Easier: compare raw coordinates of word with raw table coordinates
                            tx0, ty0, tx1, ty1 = raw_bbox
                            # check if word is fully inside the table boundaries
                            if (word_x0 >= tx0 - 2 and word_x1 <= tx1 + 2 and
                                    word_y0 >= ty0 - 2 and word_y1 <= ty1 + 2):
                                is_inside_table = True
                                break

                        if not is_inside_table:
                            non_table_words.append(w)

                    # Group remaining non-table words into paragraphs
                    # Simple heuristic: group words sharing similar y levels (lines) and group lines into paragraphs
                    if non_table_words:
                        # Sort words top-to-bottom, then left-to-right
                        non_table_words.sort(key=lambda x: (x["top"], x["x0"]))
                        
                        # Group words into blocks using vertical gap thresholding
                        paragraphs: List[List[Dict[str, Any]]] = []
                        current_paragraph: List[Dict[str, Any]] = []
                        last_bottom: Optional[float] = None

                        for word in non_table_words:
                            w_top = float(word["top"])
                            w_bottom = float(word["bottom"])

                            if last_bottom is None:
                                current_paragraph.append(word)
                            # If vertical gap exceeds threshold, start a new paragraph block
                            elif w_top - last_bottom > 15:  # threshold gap of 15 pixels
                                if current_paragraph:
                                    paragraphs.append(current_paragraph)
                                current_paragraph = [word]
                            else:
                                current_paragraph.append(word)
                            
                            last_bottom = w_bottom

                        if current_paragraph:
                            paragraphs.append(current_paragraph)

                        # Format paragraph blocks as text items
                        for p_idx, p_words in enumerate(paragraphs):
                            # Calculate paragraph bounding box coordinates
                            px0 = min(float(w["x0"]) for w in p_words)
                            py0 = min(float(w["top"]) for w in p_words)
                            px1 = max(float(w["x1"]) for w in p_words)
                            py1 = max(float(w["bottom"]) for w in p_words)

                            p_text = " ".join(w["text"] for w in p_words)
                            cleaned_text = clean_whitespace(p_text)
                            if not cleaned_text:
                                continue

                            # Detect headers (heuristic: short lines or capital structures)
                            item_type = "TEXT"
                            if len(cleaned_text) < 100 and (cleaned_text.isupper() or cleaned_text.istitle()):
                                item_type = "HEADER"

                            normalized_bbox = normalize_bbox([px0, py0, px1, py1], page_width, page_height)
                            
                            parsed_items.append(
                                ParsedItem(
                                    id=str(uuid.uuid4()),
                                    type=item_type,
                                    text=cleaned_text,
                                    page_number=page_number,
                                    bounding_box=normalized_bbox,
                                    metadata={"block_index": p_idx}
                                )
                            )

            logger.info(
                "PDF parsing completed successfully",
                file_path=file_path,
                total_items=len(parsed_items)
            )

            return ParsedDocument(
                document_id=document_id,
                ticker=ticker,
                period=period,
                year=year,
                items=parsed_items
            )

        except Exception as e:
            logger.exception("Failed to parse PDF document structures.")
            raise PipelineException(
                f"PDF parsing error occurred: {e}",
                error_code="PARSING_FAILED"
            )
