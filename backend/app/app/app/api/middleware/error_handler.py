"""Global exception handlers for structured JSON error responses."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.responses import JSONResponse

logger = structlog.get_logger("api.error")


class AppError(Exception):
    """Base application error with HTTP status code and error type."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred.") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message)


class ValidationErrorDetail(AppError):
    """Raised when input data fails validation."""

    status_code = 422
    code = "UNPROCESSABLE_ENTITY"

    def __init__(self, message: str = "Validation failed.") -> None:
        super().__init__(message)


class RateLimitError(AppError):
    """Raised when the client exceeds the rate limit."""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Too many requests. Retry after later.") -> None:
        super().__init__(message)


class UnauthorizedError(AppError):
    """Raised when authentication is missing or invalid."""

    status_code = 401
    code = "UNAUTHORIZED"

    def __init__(self, message: str = "Missing or invalid authentication token.") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    """Raised when the user lacks required permissions."""

    status_code = 403
    code = "FORBIDDEN"

    def __init__(self, message: str = "Insufficient permissions.") -> None:
        super().__init__(message)


def _get_request_id(request: Request) -> str:
    """Extract request ID from request state, defaulting to 'unknown'."""
    return getattr(request.state, "request_id", "unknown")


def _build_error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    status_code: int,
    details: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a structured error response body matching the API spec.

    Returns:
        dict with nested ``error`` object containing code, message,
        request_id, optional details, and ISO-8601 timestamp.
    """
    body: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.warning(
            "app_error",
            error_code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_response(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                status_code=exc.status_code,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        details = [
            {
                "field": ".".join(str(loc) for loc in e["loc"]),
                "issue": e["msg"],
            }
            for e in exc.errors()
        ]
        logger.warning(
            "request_validation_error",
            details=details,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=422,
            content=_build_error_response(
                code="UNPROCESSABLE_ENTITY",
                message="Request validation failed.",
                request_id=request_id,
                status_code=422,
                details=details,
            ),
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        details = [
            {
                "field": ".".join(str(loc) for loc in e["loc"]),
                "issue": e["msg"],
            }
            for e in exc.errors()
        ]
        logger.warning(
            "pydantic_validation_error",
            details=details,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=422,
            content=_build_error_response(
                code="UNPROCESSABLE_ENTITY",
                message="Validation failed.",
                request_id=request_id,
                status_code=422,
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            message=str(exc),
            request_id=request_id,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=_build_error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                request_id=request_id,
                status_code=500,
            ),
        )
