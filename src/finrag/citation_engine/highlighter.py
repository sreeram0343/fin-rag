import io
from typing import Dict, Union

import structlog
from PIL import Image, ImageDraw

logger = structlog.get_logger(__name__)


def highlight_coordinate_region(
    image_bytes: bytes,
    bbox: Dict[str, float],
) -> bytes:
    """Overlay a translucent highlight rectangle with border outlines over the page image.

    Args:
        image_bytes: The source PNG page image bytes.
        bbox: Dictionary with keys 'x1', 'y1', 'x2', 'y2' representing [0, 1000] bounds.

    Returns:
        The modified PNG image bytes.
    """
    logger.info("Highlighting image bounding box", bbox=bbox)
    try:
        # Load image and ensure alpha channel exists
        base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        width, height = base_img.size

        # Parse bounds and clip coordinates to [0, 1000] safety limits
        x1 = max(0.0, min(1000.0, float(bbox.get("x1", 0.0))))
        y1 = max(0.0, min(1000.0, float(bbox.get("y1", 0.0))))
        x2 = max(0.0, min(1000.0, float(bbox.get("x2", 1000.0))))
        y2 = max(0.0, min(1000.0, float(bbox.get("y2", 1000.0))))

        # Map normalized bounds [0, 1000] to raw pixel dimensions
        px1 = (x1 / 1000.0) * width
        py1 = (y1 / 1000.0) * height
        px2 = (x2 / 1000.0) * width
        py2 = (y2 / 1000.0) * height

        # Draw translucent yellow box with red outline
        draw.rectangle(
            [px1, py1, px2, py2],
            fill=(255, 242, 0, 80),  # Yellow translucency
            outline=(255, 0, 0, 200),  # Red border outline
            width=2
        )

        # Alpha composite overlay onto original base image
        final_img = Image.alpha_composite(base_img, overlay).convert("RGB")

        # Export to PNG bytes
        out_buf = io.BytesIO()
        final_img.save(out_buf, format="PNG")
        return out_buf.getvalue()

    except Exception as e:
        logger.exception("Failed to overlay coordinate highlights")
        raise RuntimeError(f"Highlight rendering failed: {e}")
