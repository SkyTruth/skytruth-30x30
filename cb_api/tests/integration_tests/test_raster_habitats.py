"""The raster habitats query in src/services/raster.py, against a PostGIS database.

The `raster_habitats` fixture in tests/conftest.py describes the tiles these tests draw over.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.main import app, get_engine
from src.services.constants import MANGROVES, TERRESTRIAL_HABITATS
from src.services.raster import get_raster_habitats_stats
from tests.integration_tests.helpers import (
    MAX_DEGREE_CELL_AT_50N_KM2,
    MIN_DEGREE_CELL_AT_50N_KM2,
    box,
)

pytestmark = pytest.mark.integration


def stats(engine: Engine, geometry: dict) -> dict:
    return get_raster_habitats_stats(engine, geometry, TERRESTRIAL_HABITATS)


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


def test_mangroves_are_read_from_their_own_raster(raster_habitats: Engine):
    """Mangroves share pixel value 1 with forest, so only the table and classes passed
    in tell them apart. AAA's mangroves are its first four columns."""
    result = get_raster_habitats_stats(raster_habitats, box(0, 0, 1, 1), MANGROVES)

    habitats = by_habitat(result)
    assert list(habitats) == ["mangroves"]
    assert habitats["mangroves"]["AAA"] == pytest.approx(0.4 * result["total_area"], rel=0.01)


def post_habitats(engine: Engine, habitat: str) -> dict:
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = TestClient(app).post(
            "/habitats", json={"geometry": box(0, 0, 1, 1), "habitat": habitat}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    return by_habitat(response.json())


def test_the_route_reads_the_terrestrial_raster_table(raster_habitats: Engine):
    assert sorted(post_habitats(raster_habitats, "terrestrial-habitats")["forest"]) == ["AAA"]


def test_the_route_reads_the_mangrove_raster_table(raster_habitats: Engine):
    assert list(post_habitats(raster_habitats, "mangroves")) == ["mangroves"]
