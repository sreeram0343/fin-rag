import os
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from finrag.api.dependencies import get_document_repository, get_storage, verify_token
from finrag.citation_engine.highlighter import highlight_coordinate_region
from finrag.citation_engine.pdf_renderer import get_pdf_page_count
from finrag.db.document_repository import DocumentRepository
from finrag.utils.storage import BaseStorageClient
from finrag.viewer.page_renderer import PageRenderer
from finrag.viewer.thumbnail_generator import generate_page_thumbnail

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Viewer"])

# Shared page renderer singleton
_renderer = PageRenderer()


async def _resolve_local_pdf(
    document_id: str,
    repo: DocumentRepository,
    storage: BaseStorageClient,
) -> str:
    """Download the PDF from storage to local temporary cache if not already present."""
    temp_dir = os.path.join(os.getcwd(), "temp", "docs")
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, f"{document_id}.pdf")

    if os.path.exists(local_path):
        return local_path

    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document identifier does not exist."
        )

    try:
        logger.info("Downloading PDF to local cache", doc_id=document_id, uri=doc.storage_uri)
        file_bytes = await storage.download_file(doc.storage_uri)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return local_path
    except Exception as e:
        logger.exception("Failed to retrieve document file from storage", doc_id=document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve file from object store: {e}"
        )


@router.get("/{document_id}/page/{page}")
async def get_document_page(
    document_id: str,
    page: int,
    resolution: int = Query(default=150, ge=72, le=300),
    repo: DocumentRepository = Depends(get_document_repository),
    storage: BaseStorageClient = Depends(get_storage),
    token_payload: dict = Depends(verify_token),
) -> Response:
    """Render and return high resolution PNG image of the requested page."""
    # 1. Enforce RBAC
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # 2. Get local file path
    local_path = await _resolve_local_pdf(document_id, repo, storage)

    # 3. Check page count bounds
    try:
        page_count = get_pdf_page_count(local_path)
        if page < 1 or page > page_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Page {page} is out of range. Document has {page_count} pages."
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse document page structure: {e}"
        )

    # 4. Render page
    try:
        img_bytes = _renderer.render_page(local_path, page, resolution)
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        logger.exception("Failed to render page image", doc_id=document_id, page=page)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rendering failed: {e}"
        )


@router.get("/{document_id}/highlight")
async def get_document_highlight(
    document_id: str,
    page: int = Query(..., ge=1),
    x1: float = Query(..., ge=0.0, le=1000.0),
    y1: float = Query(..., ge=0.0, le=1000.0),
    x2: float = Query(..., ge=0.0, le=1000.0),
    y2: float = Query(..., ge=0.0, le=1000.0),
    resolution: int = Query(default=150, ge=72, le=300),
    repo: DocumentRepository = Depends(get_document_repository),
    storage: BaseStorageClient = Depends(get_storage),
    token_payload: dict = Depends(verify_token),
) -> Response:
    """Render a page and return it with translucent overlays drawn over the bounding-box bounds."""
    # 1. Enforce RBAC
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # 2. Resolve document and render the base page image
    local_path = await _resolve_local_pdf(document_id, repo, storage)
    
    try:
        page_count = get_pdf_page_count(local_path)
        if page < 1 or page > page_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Page {page} is out of range."
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filing format error: {e}"
        )

    try:
        # Get base image bytes
        base_bytes = _renderer.render_page(local_path, page, resolution)
        # Apply visual highlight overlay
        bbox = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        highlighted_bytes = highlight_coordinate_region(base_bytes, bbox)
        return Response(content=highlighted_bytes, media_type="image/png")
    except Exception as e:
        logger.exception("Failed to render coordinates highlights page", doc_id=document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Highlight overlay rendering failed: {e}"
        )


@router.get("/{document_id}/thumbnail/{page}")
async def get_document_page_thumbnail(
    document_id: str,
    page: int,
    repo: DocumentRepository = Depends(get_document_repository),
    storage: BaseStorageClient = Depends(get_storage),
    token_payload: dict = Depends(verify_token),
) -> Response:
    """Render and return page navigation thumbnail image scaled to 150x200."""
    # 1. Enforce RBAC
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # 2. Resolve document and render low-res thumbnail
    local_path = await _resolve_local_pdf(document_id, repo, storage)
    try:
        # Render a low resolution page first (e.g. 72 dpi) to save processing
        base_page = _renderer.render_page(local_path, page, resolution=72)
        # Generate smaller size thumbnail bytes
        thumb_bytes = generate_page_thumbnail(base_page, (150, 200))
        return Response(content=thumb_bytes, media_type="image/png")
    except Exception as e:
        logger.exception("Failed to render thumbnail", doc_id=document_id, page=page)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thumbnail rendering failed: {e}"
        )
