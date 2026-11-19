"""The raster habitats query in src/analysis.py, against a PostGIS database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.analysis import (
    TERRESTRIAL_HABITAT_CLASSES,
    TERRESTRIAL_HABITATS_TABLE,
    get_raster_habitats_stats,
)
from src.main import app, get_engine
from tests.integration_tests.helpers import (
    MAX_DEGREE_CELL_AT_50N_KM2,
    MIN_DEGREE_CELL_AT_50N_KM2,
    box,
)

pytestmark = pytest.mark.integration


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


def stats(engine: Engine, geometry: dict) -> dict:
    return get_raster_habitats_stats(
        engine, geometry, TERRESTRIAL_HABITATS_TABLE, TERRESTRIAL_HABITAT_CLASSES
    )


def by_habitat(result: dict) -> dict[str, dict[str, float]]:
    habitats = {}
    for location in result["locations"]:
        for area in location["habitats"]:
            habitats.setdefault(area["habitat"], {})[location["code"]] = area["added_area"]
    return habitats


def test_each_habitat_gets_its_share_of_the_pixels(raster_habitats: Engine):
    """The drawing is exactly AAA's tile: half forest, three tenths savanna."""
    result = stats(raster_habitats, box(0, 0, 1, 1))

    habitats = by_habitat(result)
    assert habitats["forest"]["AAA"] == pytest.approx(0.5 * result["total_area"], rel=0.01)
    assert habitats["savanna"]["AAA"] == pytest.approx(0.3 * result["total_area"], rel=0.01)


def test_other_and_protected_pixels_are_left_out(raster_habitats: Engine):
    """The "Other" and nodata columns are a fifth of the tile, so the habitats reported
    add up to four fifths of it."""
    result = stats(raster_habitats, box(0, 0, 1, 1))

    reported = sum(area for areas in by_habitat(result).values() for area in areas.values())
    assert reported == pytest.approx(0.8 * result["total_area"], rel=0.01)


def test_each_location_lists_only_its_habitats_in_class_order(raster_habitats: Engine):
    result = stats(raster_habitats, box(0, 0, 1, 1))

    assert result["locations"][0]["code"] == "AAA"
    assert [area["habitat"] for area in result["locations"][0]["habitats"]] == [
        "forest",
        "savanna",
    ]


def test_each_location_is_reported_separately(raster_habitats: Engine):
    """BBB is all forest, so it has twice the forest of AAA."""
    result = stats(raster_habitats, box(0, 0, 2, 1))

    forest = by_habitat(result)["forest"]
    assert sorted(forest) == ["AAA", "BBB"]
    assert forest["BBB"] == pytest.approx(2 * forest["AAA"], rel=0.01)


def test_only_pixels_centred_inside_the_drawing_count(raster_habitats: Engine):
    """The drawing covers AAA's first three forest columns, and none of its savanna."""
    result = stats(raster_habitats, box(0, 0, 0.3, 1))

    habitats = by_habitat(result)
    assert habitats["forest"]["AAA"] == pytest.approx(result["total_area"], rel=0.01)
    assert "savanna" not in habitats


def test_an_area_touching_no_habitat_lists_no_locations(raster_habitats: Engine):
    result = stats(raster_habitats, box(50, 50, 51, 51))

    assert result["locations"] == []
    assert MIN_DEGREE_CELL_AT_50N_KM2 < result["total_area"] < MAX_DEGREE_CELL_AT_50N_KM2


def test_the_route_reads_the_raster_table(raster_habitats: Engine):
    app.dependency_overrides[get_engine] = lambda: raster_habitats
    try:
        response = TestClient(app).post("/terrestrial-habitats", json={"geometry": box(0, 0, 1, 1)})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert sorted(by_habitat(response.json())["forest"]) == ["AAA"]
