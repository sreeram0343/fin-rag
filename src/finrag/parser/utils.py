import re
from typing import List
from finrag.parser.base import BoundingBox

def normalize_bbox(
    bbox: List[float],
    page_width: float,
    page_height: float,
    scale_target: float = 1000.0
) -> BoundingBox:
    """Normalize raw layout float positions to integer scale [0, 1000] for spatial tracking.
    
    Coordinates are assumed to be [x0, y0, x1, y1].
    """
    if not page_width or not page_height:
        return BoundingBox(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3])
        
    x0 = min(max(0.0, (bbox[0] / page_width) * scale_target), scale_target)
    y0 = min(max(0.0, (bbox[1] / page_height) * scale_target), scale_target)
    x1 = min(max(0.0, (bbox[2] / page_width) * scale_target), scale_target)
    y1 = min(max(0.0, (bbox[3] / page_height) * scale_target), scale_target)
    
    return BoundingBox(
        x0=round(x0, 2),
        y0=round(y0, 2),
        x1=round(x1, 2),
        y1=round(y1, 2)
    )

def clean_whitespace(text: str) -> str:
    """Remove consecutive spaces, tabs, and format trailing whitespaces."""
    if not text:
        return ""
    # Replace multiple spaces/tabs with single space
    cleaned = re.sub(r"[ \t]+", " ", text)
    # Remove leading/trailing space on each line
    lines = [line.strip() for line in cleaned.splitlines()]
    # Join with clean newlines and drop empty lines
    return "\n".join(line for line in lines if line)

def is_overlapping(box_a: BoundingBox, box_b: BoundingBox) -> bool:
    """Check if two bounding boxes intersect on 2D layout canvas."""
    # Check if box_a is to the left of box_b
    if box_a.x1 < box_b.x0 or box_b.x1 < box_a.x0:
        return False
    # Check if box_a is above box_b (assuming y increases downwards)
    if box_a.y1 < box_b.y0 or box_b.y1 < box_a.y0:
        return False
    return True
