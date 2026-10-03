"""API error handling."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Application-level error with a stable JSON representation."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
        status_code: int = 400,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_exception_handlers(app) -> None:
    """Register application-level exception handlers on the FastAPI app."""
    app.add_exception_handler(AppError, _handle_app_error)
