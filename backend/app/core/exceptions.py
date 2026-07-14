"""Centralized application exceptions and FastAPI exception handlers.

Every error leaving the API is normalized into a single JSON shape:

    {
        "success": false,
        "message": "<human-readable summary>",
        "error": "<detail>",
        "status_code": <int>
    }
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, handled application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Application error."

    def __init__(self, error: str) -> None:
        """Store the detailed error string.

        Args:
            error: Human-readable detail describing what went wrong.
        """
        super().__init__(error)
        self.error = error


class ValidationAppError(AppError):
    """Raised when an uploaded file fails validation."""

    status_code = status.HTTP_400_BAD_REQUEST
    message = "Invalid upload."


class FileTooLargeError(AppError):
    """Raised when an uploaded file exceeds the size limit."""

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    message = "File too large."


class OCRProcessingError(AppError):
    """Raised when the OCR pipeline fails."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "OCR processing failed."


def _error_response(status_code: int, message: str, error: str) -> JSONResponse:
    """Build the standard error JSON response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "error": error,
            "status_code": status_code,
        },
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application.

    Args:
        application: The FastAPI app instance being configured.
    """

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Convert expected application errors into standard JSON."""
        logger.warning(
            "%s on %s %s: %s",
            type(exc).__name__,
            request.method,
            request.url.path,
            exc.error,
        )
        return _error_response(exc.status_code, exc.message, exc.error)

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Normalize framework HTTP errors (404, 405, ...)."""
        detail = str(exc.detail) if exc.detail else "HTTP error."
        return _error_response(exc.status_code, "Request failed.", detail)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Normalize FastAPI request validation errors (422)."""
        first = exc.errors()[0] if exc.errors() else {}
        detail = first.get("msg", "Invalid request.")
        location = ".".join(str(part) for part in first.get("loc", ()))
        error = f"{location}: {detail}" if location else detail
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation error.", error
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all so unexpected errors never leak stack traces."""
        logger.error(
            "Unhandled error on %s %s: %s", request.method, request.url.path, exc
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error.",
            "An unexpected error occurred.",
        )
