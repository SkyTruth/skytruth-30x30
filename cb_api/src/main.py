import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from src.config import get_settings
from src.db import create_db_engine
from src.errors import register_error_handlers

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
    allow_origins=["*"],
    allow_methods=["GET", "PUT", "POST", "HEAD"],
    allow_headers=["Content-Type"],
    max_age=3600,
)

register_error_handlers(app)


def get_engine(request: Request) -> Engine:
    """Hand routes the pooled engine, and give tests one point to override."""
    return request.app.state.engine


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
