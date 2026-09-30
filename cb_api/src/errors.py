import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import ALLOWED_ORIGINS

logger = logging.getLogger(__name__)


class BadRequestError(Exception):
    """The caller sent a request they can fix."""


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer 400 with the standard error body rather than FastAPI's 422."""
    logger.warning("Rejected request body: %s", exc.errors())
    return JSONResponse(status_code=400, content={"error": "Invalid request body"})


async def handle_bad_request_error(request: Request, exc: BadRequestError) -> JSONResponse:
    logger.warning("Rejected request", exc_info=exc)
    return JSONResponse(status_code=400, content={"error": str(exc)})


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Runs outside CORSMiddleware, so it sets the CORS header itself."""
    logger.error("Unhandled error", exc_info=exc)
    headers = {"Vary": "Origin"}
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Map exceptions in the form: {"error": <message>}, 400
    when the caller can fix it and 500 when they cannot.
    """
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(BadRequestError, handle_bad_request_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
