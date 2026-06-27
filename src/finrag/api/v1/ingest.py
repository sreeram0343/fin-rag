import os
import re
import hashlib
import uuid
import datetime
import structlog
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException, status, Query
from celery.result import AsyncResult

from finrag.api.dependencies import get_document_repository, get_chunk_repository, get_storage, verify_token
from finrag.db.models.document import Document
from finrag.db.document_repository import DocumentRepository
from finrag.db.chunk_repository import ChunkRepository
from finrag.utils.storage import BaseStorageClient
from finrag.tasks.document_tasks import process_document_task, process_document_async

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Ingestion"])

@router.post("", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ticker: str = Form(...),
    period: str = Form(...),
    year: int = Form(...),
    repo: DocumentRepository = Depends(get_document_repository),
    storage: BaseStorageClient = Depends(get_storage),
    token_payload: dict = Depends(verify_token)
) -> dict:
    """Upload filing PDF, save to storage, and schedule background parsing."""
    # 1. Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "write:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: write:documents"
        )

    # 2. Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing."
        )
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".html", ".txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF, HTML, or TXT files are allowed."
        )

    # 3. Validate metadata fields
    ticker = ticker.strip().upper()
    if not re.match(r"^[A-Z0-9]{1,5}$", ticker):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker must contain 1-5 capital alphanumeric characters (e.g. AAPL)."
        )
    period = period.strip().upper()
    if not re.match(r"^(Q[1-4]|FY|H[1-2])$", period):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Period must match Q1-Q4, FY, or H1-H2."
        )
    if not (1990 <= year <= 2100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Year must fall in range [1990, 2100]."
        )

    # 4. Read file content and check size limit (150MB)
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > 150:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum size of 150MB."
        )

    # 5. Compute SHA-256 hash for deduplication
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_doc = await repo.get_by_hash(file_hash)
    if existing_doc:
        logger.info("Deduplication triggered, document already parsed", file_hash=file_hash, doc_id=existing_doc.id)
        return {
            "job_id": existing_doc.id,
            "document_id": existing_doc.id,
            "status": existing_doc.status,
            "ticker": existing_doc.ticker,
            "period": existing_doc.period,
            "year": existing_doc.year,
            "created_at": existing_doc.created_at.isoformat() + "Z"
        }

    # 6. Upload file to configured storage
    unique_filename = f"{uuid.uuid4()}{ext}"
    storage_uri = await storage.upload_file(file_bytes, unique_filename)

    # 7. Write record into database
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        ticker=ticker,
        period=period,
        year=year,
        storage_uri=storage_uri,
        file_hash=file_hash,
        status="QUEUED",
        created_at=datetime.datetime.utcnow()
    )
    await repo.save(doc)
    await repo.session.commit()

    # 8. Dispatch parsing task to Celery with fallback to BackgroundTasks
    try:
        # apply_async lets us explicitly set the task ID to the doc_id
        process_document_task.apply_async(args=[doc_id], task_id=doc_id)
        logger.info("Successfully scheduled Celery task for document processing", doc_id=doc_id)
    except Exception as e:
        logger.warning(
            "Celery queue is unavailable. Falling back to FastAPI BackgroundTasks.",
            doc_id=doc_id,
            error=str(e)
        )
        background_tasks.add_task(process_document_async, doc_id)

    return {
        "job_id": doc_id,
        "document_id": doc_id,
        "status": "QUEUED",
        "ticker": ticker,
        "period": period,
        "year": year,
        "created_at": doc.created_at.isoformat() + "Z"
    }


@router.get("")
async def list_documents(
    ticker: str = Query(default=None, description="Filter by company ticker symbol"),
    repo: DocumentRepository = Depends(get_document_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    token_payload: dict = Depends(verify_token)
) -> dict:
    """List uploaded documents with optional ticker filtering."""
    # Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # Validate ticker if provided
    if ticker:
        ticker = ticker.strip().upper()
        if not re.match(r"^[A-Z0-9]{1,5}$", ticker):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticker must contain 1-5 capital alphanumeric characters."
            )

    documents = await repo.list_all(ticker=ticker)

    results = []
    for doc in documents:
        chunk_count = await chunk_repo.count_by_document_id(doc.id)
        results.append({
            "document_id": doc.id,
            "ticker": doc.ticker,
            "period": doc.period,
            "year": doc.year,
            "status": doc.status,
            "chunk_count": chunk_count,
            "created_at": doc.created_at.isoformat() + "Z"
        })

    return {"documents": results, "total": len(results)}


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    repo: DocumentRepository = Depends(get_document_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    token_payload: dict = Depends(verify_token)
) -> dict:
    """Retrieve detailed metadata for a specific document."""
    # Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # Validate UUID format
    if not re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", document_id, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document ID must be a valid 36-character UUID string."
        )

    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    chunk_count = await chunk_repo.count_by_document_id(document_id)
    chunks = await chunk_repo.get_by_document_id(document_id)

    chunk_summary = {
        "total": chunk_count,
        "by_type": {},
        "pages": set(),
    }
    for chunk in chunks:
        chunk_summary["by_type"][chunk.chunk_type] = chunk_summary["by_type"].get(chunk.chunk_type, 0) + 1
        chunk_summary["pages"].add(chunk.page_number)

    return {
        "document_id": doc.id,
        "ticker": doc.ticker,
        "period": doc.period,
        "year": doc.year,
        "status": doc.status,
        "storage_uri": doc.storage_uri,
        "file_hash": doc.file_hash,
        "created_at": doc.created_at.isoformat() + "Z",
        "chunks": {
            "total": chunk_count,
            "by_type": chunk_summary["by_type"],
            "pages_covered": sorted(chunk_summary["pages"]),
        }
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    repo: DocumentRepository = Depends(get_document_repository),
    token_payload: dict = Depends(verify_token)
) -> dict:
    """Retrieve parsing pipeline status for a scheduled job."""
    # 1. Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "read:documents" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:documents"
        )

    # 2. Validate UUID format
    if not re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", job_id, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job ID must be a valid 36-character UUID string."
        )

    # 3. Retrieve document from database
    doc = await repo.get_by_id(job_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job identifier does not exist."
        )

    # 4. Check Celery task state if available
    celery_status = None
    try:
        res = AsyncResult(job_id)
        if res.state != "PENDING":
            celery_status = res.state
    except Exception:
        pass

    status_mapping = {
        "PENDING": "QUEUED",
        "STARTED": "PROCESSING",
        "PROGRESS": "PROCESSING",
        "SUCCESS": "COMPLETED",
        "FAILURE": "FAILED"
    }

    db_status = doc.status
    current_status = status_mapping.get(celery_status, db_status)

    # Enhanced status tracking with new pipeline stages
    progress = 0
    step = "INGESTION"
    if current_status == "QUEUED":
        step = "QUEUED"
        progress = 5
    elif current_status == "PROCESSING":
        step = "OCR_PARSING"
        progress = 25
    elif current_status == "CHUNKING":
        step = "SEMANTIC_CHUNKING"
        progress = 50
    elif current_status == "INDEXING":
        step = "VECTOR_INDEXING"
        progress = 75
    elif current_status == "COMPLETED":
        step = "COMPLETED"
        progress = 100
    elif current_status == "FAILED":
        step = "FAILED"
        progress = 100

    return {
        "job_id": job_id,
        "status": current_status,
        "current_step": step,
        "progress_percentage": progress,
        "error": "Pipeline processing failed." if current_status == "FAILED" else None
    }
