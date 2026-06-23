import time
import uuid
from contextlib import asynccontextmanager
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import structlog
from finrag.core.config import settings
from finrag.core.exceptions import ApiException
from finrag.core.logging import configure_logging, correlation_id_var
from finrag.api.v1.router import router as api_v1_router

# Setup structured logs configuration
configure_logging(settings.LOG_LEVEL, settings.ENV)
logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events listener for FastAPI app."""
    logger.info("Initializing FinRAG application services.", env=settings.ENV)
    yield
    logger.info("Shutting down FinRAG application services.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(api_v1_router, prefix="/api/v1")

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    """Injects correlation ID tracing headers and measures request latencies."""
    start_time = time.perf_counter()
    
    # Retrieve correlation ID from headers or generate a new UUID
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
        
    # Bind the token context variable
    token = correlation_id_var.set(correlation_id)
    
    # Bind structlog context variables
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    try:
        response: Response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=f"{process_time:.4f}s"
        )
        return response
    finally:
        # Unbind structlog variables and reset context vars
        structlog.contextvars.unbind_contextvars("correlation_id")
        correlation_id_var.reset(token)

@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Translates pipeline/API exceptions into structured JSON responses."""
    correlation_id = correlation_id_var.get()
    logger.error(
        "API error occurred",
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
          "error": {
            "code": exc.error_code,
            "message": exc.message,
            "correlation_id": correlation_id,
            "details": exc.details
          }
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions."""
    correlation_id = correlation_id_var.get()
    logger.exception("Unhandled error occurred in server application.")
    return JSONResponse(
        status_code=500,
        content={
          "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred in the system.",
            "correlation_id": correlation_id,
            "details": []
          }
        }
    )

@app.get("/health")
async def health_check() -> dict:
    """Simple API check confirming server application health."""
    return {"status": "healthy", "project": settings.PROJECT_NAME}
