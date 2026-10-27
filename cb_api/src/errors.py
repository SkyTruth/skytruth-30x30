import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import ALLOWED_ORIGINS

logger = logging.getLogger(__name__)


class BadRequestError(Exception):
    """The caller sent a request they can fix."""


def describe_validation_error(errors: Sequence[Mapping[str, Any]]) -> str:
    """A specific message naming what is wrong with the request body."""
    by_field = {error["loc"]: error for error in errors}

    geometry = by_field.get(("body", "geometry"))
    if geometry:
        # Missing, null, and {} count as absent
        if geometry["type"] == "missing" or not geometry.get("input"):
            return "Geometry is required"
        return "Invalid geometry: expected a GeoJSON object"

    if ("body", "environment") in by_field:
        return "Environment must be one of `marine` or `terrestrial`"

    for error in errors:
        loc = error["loc"]
        if error["type"] == "json_invalid":
            return "Request body is not valid JSON"
        if loc == ("body",):
            return "Request body must be a JSON object"
        if len(loc) > 1 and isinstance(loc[1], str):
            field = loc[1]
            if error["type"] == "missing":
                return f"{field.capitalize()} is required"
            return f"Invalid {field}"

    return "Invalid request body"


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer 400 with the standard error body rather than FastAPI's 422.

    The validation detail is logged, not returned.
    """
    logger.warning("Rejected request body: %s", exc.errors())
    return JSONResponse(status_code=400, content={"error": describe_validation_error(exc.errors())})


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
