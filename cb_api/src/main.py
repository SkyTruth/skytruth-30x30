import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from src.analysis import get_locations_stats
from src.config import ALLOWED_ORIGINS, get_settings
from src.db import create_db_engine
from src.errors import BadRequestError, register_error_handlers
from src.schemas import AnalysisRequest, Environment, LocationStats, ProtectionLevelRequest

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Connect to the database and store the pooled engine on app.state."""
    engine = create_db_engine(get_settings())
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Conservation Builder API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "PUT", "POST", "HEAD"],
    allow_headers=["Content-Type"],
    max_age=3600,
)

register_error_handlers(app)


def get_engine(request: Request) -> Engine:
    """Hand routes the pooled engine, and give tests one point to override."""
    return request.app.state.engine


PooledEngine = Annotated[Engine, Depends(get_engine)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/coverage", response_model=LocationStats)
@app.post("/", response_model=LocationStats, deprecated=True)
def coverage(body: AnalysisRequest, engine: PooledEngine) -> dict:
    """How much of the given area is already protected, broken down by location."""
    return get_locations_stats(engine, body.geometry, body.environment.table)


@app.post("/protection-level", response_model=LocationStats)
def protection_level(body: ProtectionLevelRequest, engine: PooledEngine) -> dict:
    """How much of the given area is protected at `level`, broken down by location."""
    if body.level.marine_only and body.environment is not Environment.MARINE:
        raise BadRequestError(
            f"{body.level} is not available for the {body.environment} environment"
        )
    return get_locations_stats(engine, body.geometry, body.level.table)
