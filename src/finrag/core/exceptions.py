from typing import Any, Dict, List, Optional

class FinRAGException(Exception):
    """Root system exception for the FinRAG platform."""
    pass

class ApiException(FinRAGException):
    """Base exception for all HTTP-facing errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or []

class AuthException(ApiException):
    """Thrown during authentication or authorization breaches."""
    def __init__(
        self,
        message: str = "Authentication failed.",
        error_code: str = "UNAUTHORIZED",
        details: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        super().__init__(message, status_code=401, error_code=error_code, details=details)

class ValidationException(ApiException):
    """Thrown when incoming payload constraints fail validation."""
    def __init__(
        self,
        message: str = "Validation failed.",
        details: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        super().__init__(message, status_code=422, error_code="VALIDATION_FAILED", details=details)

class ResourceNotFoundException(ApiException):
    """Thrown when target resource is not found."""
    def __init__(
        self,
        message: str = "Target resource could not be found.",
        error_code: str = "RESOURCE_NOT_FOUND",
        details: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        super().__init__(message, status_code=404, error_code=error_code, details=details)

class PipelineException(ApiException):
    """Thrown when parsing, index loading, or reasoning pipelines fail."""
    def __init__(
        self,
        message: str,
        error_code: str = "PIPELINE_FAILED",
        details: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        super().__init__(message, status_code=502, error_code=error_code, details=details)
