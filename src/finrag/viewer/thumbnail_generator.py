import io
from typing import Tuple

import structlog
from PIL import Image

logger = structlog.get_logger(__name__)


def generate_page_thumbnail(
    image_bytes: bytes,
    dimensions: Tuple[int, int] = (150, 200),
) -> bytes:
    """Scale down the rendered page image to generate navigation thumbnails.

    Args:
        image_bytes: High resolution PNG image bytes.
        dimensions: Target (width, height) tuple bounds.

    Returns:
        Resized PNG image bytes.
    """
    logger.info("Generating page thumbnail", dims=dimensions)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # PIL thumbnail scales down preserving aspect ratio
        img.thumbnail(dimensions)

        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except Exception as e:
        logger.exception("Failed to scale thumbnail image")
        raise RuntimeError(f"Thumbnail scaling failed: {e}")
