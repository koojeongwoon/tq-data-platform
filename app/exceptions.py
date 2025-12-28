"""Custom exceptions for TQ Data Platform API"""

from typing import Any, Optional


class TQBaseException(Exception):
    """Base exception for all TQ Data Platform errors"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details
        super().__init__(self.message)


# Client Errors (4xx)
class NotFoundError(TQBaseException):
    """Resource not found (404)"""

    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(message, status_code=404, error_code="NOT_FOUND", details=details)


class ValidationError(TQBaseException):
    """Request validation error (422)"""

    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None):
        super().__init__(message, status_code=422, error_code="VALIDATION_ERROR", details=details)


class UnauthorizedError(TQBaseException):
    """Authentication required (401)"""

    def __init__(self, message: str = "Authentication required", details: Optional[Any] = None):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED", details=details)


class ForbiddenError(TQBaseException):
    """Permission denied (403)"""

    def __init__(self, message: str = "Permission denied", details: Optional[Any] = None):
        super().__init__(message, status_code=403, error_code="FORBIDDEN", details=details)


class BadRequestError(TQBaseException):
    """Bad request (400)"""

    def __init__(self, message: str = "Bad request", details: Optional[Any] = None):
        super().__init__(message, status_code=400, error_code="BAD_REQUEST", details=details)


# Server Errors (5xx)
class DatabaseError(TQBaseException):
    """Database operation failed (500)"""

    def __init__(self, message: str = "Database error", details: Optional[Any] = None):
        super().__init__(message, status_code=500, error_code="DATABASE_ERROR", details=details)


class ExternalAPIError(TQBaseException):
    """External API call failed (502)"""

    def __init__(self, message: str = "External service error", details: Optional[Any] = None):
        super().__init__(message, status_code=502, error_code="EXTERNAL_API_ERROR", details=details)


class ServiceUnavailableError(TQBaseException):
    """Service temporarily unavailable (503)"""

    def __init__(self, message: str = "Service unavailable", details: Optional[Any] = None):
        super().__init__(message, status_code=503, error_code="SERVICE_UNAVAILABLE", details=details)


class ConfigurationError(TQBaseException):
    """Configuration error (500)"""

    def __init__(self, message: str = "Configuration error", details: Optional[Any] = None):
        super().__init__(message, status_code=500, error_code="CONFIGURATION_ERROR", details=details)
