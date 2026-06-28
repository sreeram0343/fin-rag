import io
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


def get_pdf_page_count(file_path: str) -> int:
    """Retrieve total page count of target PDF document."""
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        logger.exception("Failed to get PDF page count", path=file_path)
        raise ValueError(f"Failed to read PDF pages: {e}")


def render_pdf_page_to_bytes(file_path: str, page_number: int, resolution: int = 150) -> bytes:
    """Render a specific PDF page to PNG bytes using available engines."""
    logger.info("Rendering PDF page", path=file_path, page=page_number, res=resolution)

    # Engine 1: Attempt pdfplumber (primary, whitelisted in dependencies)
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                raise IndexError(f"Page index {page_number} is out of bounds (1-{len(pdf.pages)})")
            page = pdf.pages[page_number - 1]
            # Convert to image
            im = page.to_image(resolution=resolution)
            buf = io.BytesIO()
            im.original.save(buf, format="PNG")
            return buf.getvalue()
    except ImportError:
        logger.warning("pdfplumber not installed. Trying PyMuPDF fallback.")
    except IndexError as e:
        raise e
    except Exception as e:
        logger.warning("pdfplumber rendering failed. Trying PyMuPDF fallback.", error=str(e))

    # Engine 2: Fallback to PyMuPDF (fitz)
    try:
        import fitz  # type: ignore

        doc = fitz.open(file_path)
        if page_number < 1 or page_number > len(doc):
            raise IndexError(f"Page index {page_number} is out of bounds (1-{len(doc)})")
        page = doc.load_page(page_number - 1)
        # Compute zoom matrix for resolution scaling
        zoom = resolution / 72.0  # default dpi is 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed. Trying pdf2image fallback.")
    except IndexError as e:
        raise e
    except Exception as e:
        logger.warning("PyMuPDF rendering failed. Trying pdf2image fallback.", error=str(e))

    # Engine 3: Fallback to pdf2image
    try:
        from pdf2image import convert_from_path

        pages = convert_from_path(
            file_path,
            dpi=resolution,
            first_page=page_number,
            last_page=page_number,
        )
        if not pages:
            raise IndexError(f"Page index {page_number} is out of bounds.")
        buf = io.BytesIO()
        pages[0].save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.exception("All PDF rendering engines failed")
        raise RuntimeError(f"Failed to render PDF page. No working parser/renderer available: {e}")
