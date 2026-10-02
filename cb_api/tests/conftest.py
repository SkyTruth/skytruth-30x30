import os
from collections.abc import Iterator

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.engine import Engine
from testcontainers.community.postgres import PostgresContainer

from src.analysis import AnalysisTable

POSTGIS_IMAGE = "postgis/postgis:14-3.4"


@pytest.fixture(scope="session")
def postgis() -> Iterator[Engine]:
    """Start a PostGIS container for the test session."""
    try:
        container = PostgresContainer(POSTGIS_IMAGE, driver="pg8000").start()
    except Exception as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"cannot start a PostGIS container; check if Docker is running ({exc})")

    engine = sqlalchemy.create_engine(container.get_connection_url())
    try:
        yield engine
    finally:
        engine.dispose()
        container.stop()


@pytest.fixture
def analysis_tables(postgis: Engine) -> Iterator[Engine]:
    """Create analysis tables with example data, and drop them after the test."""
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
