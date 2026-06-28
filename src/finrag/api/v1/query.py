import re
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from finrag.api.dependencies import get_orchestrator, verify_token
from finrag.agent.orchestrator import AgentOrchestrator
from finrag.utils.excel import generate_financial_excel
from finrag.utils.pdf import compile_pdf_report

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/queries", tags=["Queries"])


class AskRequest(BaseModel):
    """Pydantic schema validating user QA request payload."""

    query: str = Field(..., min_length=5, max_length=500)
    ticker: str = Field(..., pattern=r"^[A-Z0-9]{1,5}$")
    filters: Optional[Dict[str, Any]] = None


class CompareRequest(BaseModel):
    """Pydantic schema validating period-over-period comparison payload."""

    ticker: str = Field(..., pattern=r"^[A-Z0-9]{1,5}$")
    source_document_id: str
    target_document_id: str
    sections: Optional[List[str]] = None

    @field_validator("source_document_id", "target_document_id")
    @classmethod
    def validate_uuid(cls, val: str) -> str:
        """Enforce standard UUID formatting."""
        uuid_regex = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_regex, val, re.IGNORECASE):
            raise ValueError("Must be a valid 36-character UUID string.")
        return val.lower()


@router.post("/ask")
async def ask_query(
    request: AskRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    token_payload: dict = Depends(verify_token),
) -> dict:
    """Submit a query to the financial QA RAG engine with mathematical verification."""
    # 1. Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "read:queries" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:queries",
        )

    try:
        result = await orchestrator.ask(
            query=request.query,
            ticker=request.ticker,
            filters=request.filters,
        )
        return result
    except Exception as e:
        logger.exception("Failed to execute QA query", query=request.query)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error occurred in external reasoning layers: {e}",
        )


@router.post("/compare")
async def compare_disclosures(
    request: CompareRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    token_payload: dict = Depends(verify_token),
) -> dict:
    """Perform a semantic comparison of disclosures across filing periods."""
    # 1. Enforce RBAC scopes
    scopes = token_payload.get("scopes", [])
    if "read:queries" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:queries",
        )

    try:
        result = await orchestrator.compare(
            ticker=request.ticker,
            source_document_id=request.source_document_id,
            target_document_id=request.target_document_id,
            sections=request.sections,
        )
        return result
    except Exception as e:
        logger.exception(
            "Failed to execute comparative query",
            source=request.source_document_id,
            target=request.target_document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison pipeline error: {e}",
        )


class ExportPDFRequest(BaseModel):
    """Pydantic schema validating PDF export request inputs."""

    answer: str = Field(..., min_length=1)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    title: Optional[str] = "Financial Research Report"


class ExportExcelRequest(BaseModel):
    """Pydantic schema validating Excel export sheets payload."""

    sheets: Dict[str, List[List[Any]]] = Field(..., min_items=1)


@router.post("/export/pdf")
async def export_pdf_report(
    request: ExportPDFRequest,
    token_payload: dict = Depends(verify_token),
) -> Response:
    """Compile RAG text and citations into a downloadable corporate PDF report."""
    scopes = token_payload.get("scopes", [])
    if "read:queries" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:queries",
        )

    try:
        pdf_bytes = compile_pdf_report(request.answer, request.citations, request.title)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=report.pdf"},
        )
    except Exception as e:
        logger.exception("Failed to generate PDF report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {e}",
        )


@router.post("/export/excel")
async def export_excel_sheet(
    request: ExportExcelRequest,
    token_payload: dict = Depends(verify_token),
) -> Response:
    """Generate a dynamic mathematical Excel sheet mapping input tables."""
    scopes = token_payload.get("scopes", [])
    if "read:queries" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required scope: read:queries",
        )

    try:
        excel_bytes = generate_financial_excel(request.sheets)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=financials.xlsx"},
        )
    except Exception as e:
        logger.exception("Failed to generate Excel sheet")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Excel generation failed: {e}",
        )
