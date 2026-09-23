import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def describe_validation_error(exc: RequestValidationError) -> str:
    """Missing fields read '<field> is required'."""
    error = exc.errors()[0]
    field = ".".join(str(part) for part in error["loc"] if part != "body") or "body"
    if error["type"] == "missing":
        return f"{field} is required"
    return f"{field}: {error['msg']}"


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer 400 with the standard error body rather than FastAPI's 422."""
    return JSONResponse(status_code=400, content={"error": describe_validation_error(exc)})


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("Rejected request: %s", exc)
    return JSONResponse(status_code=400, content={"error": str(exc)})


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Map exceptions in the form: {"error": <message>}, 400
    when the caller can fix it and 500 when they cannot.
    """
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ValueError, handle_value_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
