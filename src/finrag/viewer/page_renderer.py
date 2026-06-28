import hashlib
import os
from typing import Optional

import structlog

from finrag.citation_engine.pdf_renderer import render_pdf_page_to_bytes

logger = structlog.get_logger(__name__)


class PageRenderer:
    """Handles PDF page image rendering with file-system caching for sub-500ms latency targets."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        if cache_dir is None:
            # Place cache folder inside local workspace temp
            cache_dir = os.path.join(os.getcwd(), "temp", "page_cache")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info("Initialized PageRenderer cache directory", path=self.cache_dir)

    def render_page(self, file_path: str, page_number: int, resolution: int = 150) -> bytes:
        """Render page from file or retrieve from the filesystem cache.

        Args:
            file_path: Absolute local path to the target PDF.
            page_number: 1-based page index.
            resolution: Rendering DPI resolution.

        Returns:
            PNG image bytes.
        """
        # Create a unique file cache signature
        file_signature = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
        cache_key = f"{file_signature}_page_{page_number}_res_{resolution}.png"
        cache_path = os.path.join(self.cache_dir, cache_key)

        # Hit cache if exists
        if os.path.exists(cache_path):
            logger.debug("Page rendering cache hit", path=file_path, page=page_number)
            try:
                with open(cache_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.warning("Failed to read cached image. Re-rendering.", error=str(e))

        # Render fresh page
        logger.info("Page rendering cache miss. Running PDF rendering.", path=file_path, page=page_number)
        img_bytes = render_pdf_page_to_bytes(file_path, page_number, resolution)

        # Save to cache asynchronously or synchronously
        try:
            with open(cache_path, "wb") as f:
                f.write(img_bytes)
        except Exception as e:
            logger.warning("Failed to write page render to cache file", path=cache_path, error=str(e))

        return img_bytes
