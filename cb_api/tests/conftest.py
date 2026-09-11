import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy
import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.analysis import AnalysisTable


def compose_database_url() -> str:
    """Build the connection URL to a local PostGIS database
    from the credentials in docker-compose.yml.
    """
    compose_file = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    compose = yaml.safe_load(compose_file.read_text(encoding="utf-8"))

    try:
        service = compose["services"]["postgis"]
        environment = service["environment"]
        published_port = str(service["ports"][0]).split(":")[0].strip('"')
        user = environment["POSTGRES_USER"]
        password = environment["POSTGRES_PASSWORD"]
        database = environment["POSTGRES_DB"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"cannot read the postgis service from {compose_file}."
        ) from exc

    return f"postgresql+pg8000://{user}:{password}@127.0.0.1:{published_port}/{database}"


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or compose_database_url()


@pytest.fixture(scope="session")
def postgis(database_url: str) -> Iterator[Engine]:
    """A connected engine, or a skip if the database is not up."""
    engine = sqlalchemy.create_engine(database_url, connect_args={"timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"no PostGIS at {database_url} — run `docker compose up -d` ({exc})")

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def analysis_tables(postgis: Engine, database_url: str) -> Iterator[Engine]:
    """Create analysis tables with example data, and drop them after the test.
    Only runs against a local database.
    """
    host = urlparse(database_url).hostname
    if host not in {"127.0.0.1", "::1", "localhost", "postgis"}:
        pytest.fail(
            f"this test only runs against a local database, not {host!r}.",
            pytrace=False,
        )

    with postgis.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS data"))
        for table in AnalysisTable:
            conn.execute(text(f"DROP TABLE IF EXISTS data.{table.value}"))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE data.{table.value} (
                        id serial PRIMARY KEY,
                        location text,
                        the_geom geometry(MultiPolygon, 4326)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO data.{table.value} (location, the_geom) VALUES
                        ('AAA', ST_Multi(ST_MakeEnvelope(0, 0, 1, 1, 4326))),
                        ('BBB', ST_Multi(ST_MakeEnvelope(1, 0, 2, 1, 4326))),
                        ('AAA', ST_Multi(ST_MakeEnvelope(2, 0, 3, 1, 4326)))
                    """
                )
            )

    try:
        yield postgis
    finally:
        with postgis.begin() as conn:
            for table in AnalysisTable:
                conn.execute(text(f"DROP TABLE IF EXISTS data.{table.value}"))
