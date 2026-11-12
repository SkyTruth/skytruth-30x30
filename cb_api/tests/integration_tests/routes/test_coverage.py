"""POST /coverage end to end, against a PostGIS database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.analysis import AnalysisTable, get_locations_stats
from tests.integration_tests.helpers import (
    MAX_DEGREE_CELL_AT_50N_KM2,
    MIN_DEGREE_CELL_AT_50N_KM2,
    box,
)

pytestmark = pytest.mark.integration


def test_the_route_returns_the_same_numbers_as_the_query(api: TestClient, analysis_tables: Engine):
    geometry = box(0, 0, 3, 1)

    response = api.post("/coverage", json={"geometry": geometry})

    assert response.status_code == 200
    assert response.json() == get_locations_stats(analysis_tables, geometry, AnalysisTable.MARINE)


def test_the_route_reads_the_terrestrial_table(api: TestClient, analysis_tables: Engine):
    geometry = box(0, 0, 3, 1)

    response = api.post("/coverage", json={"geometry": geometry, "environment": "terrestrial"})

    assert response.status_code == 200
    assert response.json() == get_locations_stats(
        analysis_tables, geometry, AnalysisTable.TERRESTRIAL
    )


def test_an_area_touching_nothing_is_an_empty_result_over_http(api: TestClient):
    response = api.post("/coverage", json={"geometry": box(50, 50, 51, 51)})

    assert response.status_code == 200
    assert response.json()["locations"] == []
    assert MIN_DEGREE_CELL_AT_50N_KM2 < response.json()["total_area"] < MAX_DEGREE_CELL_AT_50N_KM2


def test_a_line_is_a_400_over_http(api: TestClient):
    """status 400 plus 'Invalid geometry' is what the frontend branches on."""
    response = api.post(
        "/coverage", json={"geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}
    )

    assert response.status_code == 400
    assert "Invalid geometry" in response.json()["error"]


def test_a_topology_error_is_a_400_over_http(api: TestClient, analysis_tables: Engine):
    """GEOS refuses to intersect a self-intersecting polygon. A shape that triggers that
    must be flagged as invalid geometry."""
    with analysis_tables.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO data.{AnalysisTable.MARINE.value} (location, the_geom) VALUES "
                "('CCC', ST_Multi(ST_GeomFromText("
                "'POLYGON((10 10, 11 11, 11 10, 10 11, 10 10))', 4326)))"
            )
        )

    response = api.post("/coverage", json={"geometry": box(10.25, 10.25, 10.75, 10.75)})

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid geometry: input geometry could not be processed"}
