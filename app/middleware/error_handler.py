"""Global error handler middleware for FastAPI"""

import logging
import os
import traceback
from typing import Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import TQBaseException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment check
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Union[dict, list, str, None] = None,
    path: str = None
) -> JSONResponse:
    """
    Create standardized error response

    Response format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "details": {...},  # Optional, only in development
            "path": "/api/endpoint"
        }
    }
    """
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    # Add details only in development mode
    if not IS_PRODUCTION and details is not None:
        error_response["error"]["details"] = details

    if path:
        error_response["error"]["path"] = path

    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def custom_exception_handler(request: Request, exc: TQBaseException) -> JSONResponse:
    """
    Handler for custom TQ exceptions

    Example:
        raise NotFoundError("Policy not found", details={"policy_id": "WLF123"})
    """
    logger.error(
        f"Custom exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "details": exc.details
        }
    )

    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=request.url.path
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handler for FastAPI/Starlette HTTP exceptions

    Example:
        raise HTTPException(status_code=404, detail="Not found")
    """
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )

    return create_error_response(
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        path=request.url.path
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler for Pydantic validation errors

    Example:
        Request with invalid query params or request body
    """
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={
            "path": request.url.path,
            "errors": exc.errors()
        }
    )

    # Format validation errors
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=validation_errors if not IS_PRODUCTION else None,
        path=request.url.path
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for all unhandled exceptions

    This catches any exception that wasn't handled by other handlers
    """
    # Log full traceback for debugging
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "exception_type": type(exc).__name__
        },
        exc_info=True
    )

    # In production, hide implementation details
    if IS_PRODUCTION:
        message = "An internal server error occurred"
        details = None
    else:
        message = str(exc)
        details = {
            "type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message=message,
        details=details,
        path=request.url.path
    )
