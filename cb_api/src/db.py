from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL

from src.config import Settings


def build_database_url(settings: Settings) -> URL:
    return URL.create(
        drivername="postgresql+pg8000",
        username=settings.database_username,
        password=settings.database_password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
    )


def create_db_engine(settings: Settings) -> Engine:
    """Initialize the connection pool for the Cloud SQL Postgres instance.

    Creating the engine does not open a connection; the first one is established
    lazily on the first `connect()`.
    """
    return create_engine(
        build_database_url(settings),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
