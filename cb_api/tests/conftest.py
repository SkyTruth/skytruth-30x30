import os
from collections.abc import Iterator

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.engine import Engine
from testcontainers.community.postgres import PostgresContainer

from src.services.raster import TERRESTRIAL_HABITATS_TABLE
from src.services.vector import AnalysisTable

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
                        ('AAA', ST_Multi(ST_MakeEnvelope(2, 0, 3, 1, 4326))),
                        -- Named after its own table, so a request over this box shows
                        -- which table was read
                        (:table, ST_Multi(ST_MakeEnvelope(10, 0, 11, 1, 4326)))
                    """
                ),
                {"table": table.value},
            )

    try:
        yield postgis
    finally:
        with postgis.begin() as conn:
            for table in AnalysisTable:
                conn.execute(text(f"DROP TABLE IF EXISTS data.{table.value}"))


@pytest.fixture
def raster_habitats(postgis: Engine) -> Iterator[Engine]:
    """Create the terrestrial habitats raster table with one 10x10 tile of 0.1° pixels
    per location, and drop it after the test.

    AAA covers 0–1°E: columns 1–5 are forest, 6–8 savanna, 9 "Other" and 10 nodata, as
    a protected area leaves it. BBB covers 1–2°E and is all forest.
    """
    with postgis.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_raster"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS data"))
        conn.execute(text(f"DROP TABLE IF EXISTS data.{TERRESTRIAL_HABITATS_TABLE}"))
        conn.execute(
            text(
                f"""
                CREATE TABLE data.{TERRESTRIAL_HABITATS_TABLE} (
                    id serial PRIMARY KEY,
                    location text,
                    rast raster
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                INSERT INTO data.{TERRESTRIAL_HABITATS_TABLE} (location, rast)
                SELECT 'AAA', ST_SetValues(ST_SetValues(ST_SetValues(
                    ST_AddBand(
                        ST_MakeEmptyRaster(10, 10, 0, 1, 0.1, -0.1, 0, 0, 4326),
                        '8BUI'::text, 1, 0
                    ),
                    1, 6, 1, 3, 10, 2), 1, 9, 1, 1, 10, 255), 1, 10, 1, 1, 10, 0)
                UNION ALL
                SELECT 'BBB', ST_AddBand(
                    ST_MakeEmptyRaster(10, 10, 1, 1, 0.1, -0.1, 0, 0, 4326), '8BUI'::text, 1, 0
                )
                """
            )
        )

    try:
        yield postgis
    finally:
        with postgis.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS data.{TERRESTRIAL_HABITATS_TABLE}"))
