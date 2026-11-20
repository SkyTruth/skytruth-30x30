"""Route-level checks for POST /habitats."""

import pytest

from src.schemas import Habitat
from src.services.raster import TERRESTRIAL_HABITAT_CLASSES
from src.services.vector import AnalysisTable
from tests.routes.helpers import ENGINE, HABITATS_STATS, POLYGON, RouteTestClient

PATH = "/habitats"

MARINE_HABITATS = [habitat for habitat in Habitat if habitat is not Habitat.JUNG_HABITATS]


# --- the happy path ----------------------------------------------------------------


@pytest.mark.parametrize("habitat", MARINE_HABITATS)
def test_each_marine_habitat_returns_its_area_by_location(api: RouteTestClient, habitat: Habitat):
    response = api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    assert response.status_code == 200
    assert response.json() == {
        "locations": [
            {"code": "ESP", "habitats": [{"habitat": habitat.value, "added_area": 30.0}]}
        ],
        "total_area": 100.0,
    }


@pytest.mark.parametrize("habitat", MARINE_HABITATS)
def test_each_marine_habitat_reads_its_own_table(api: RouteTestClient, habitat: Habitat):
    api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    _, _, table = api.calls[0]
    assert table is habitat.table


def test_the_marine_habitats_read_distinct_tables():
    """A copy-paste slip in the enum would quietly serve one habitat's numbers
    for another."""
    tables = {habitat.table for habitat in MARINE_HABITATS}

    assert len(tables) == len(MARINE_HABITATS)


def test_jung_habitats_returns_the_raster_habitats_stats(api: RouteTestClient):
    response = api.client.post(PATH, json={"geometry": POLYGON, "habitat": "jung-habitats"})

    assert response.status_code == 200
    assert response.json() == HABITATS_STATS
    assert api.calls == [(ENGINE, POLYGON)]


def test_other_is_not_reported():
    """The progress tracker leaves "Other" out, so the two would not add up."""
    assert 255 not in TERRESTRIAL_HABITAT_CLASSES


@pytest.mark.parametrize("habitat", ["mangroves", "jung-habitats"])
def test_the_geometry_is_passed_through_untouched(api: RouteTestClient, habitat: str):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature, "habitat": habitat})

    assert api.calls[0][1] == feature


# --- rejections --------------------------------------------------------------------


def test_the_habitat_is_required(api: RouteTestClient):
    """Unlike `level`, there is no sensible default habitat."""
    response = api.client.post(PATH, json={"geometry": POLYGON})

    assert response.status_code == 400
    assert response.json() == {"error": "Habitat is required"}
    assert api.calls == []


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"habitat": "mangroves"}, "Geometry is required"),
        ({"geometry": {}, "habitat": "mangroves"}, "Geometry is required"),
        ({"geometry": POLYGON, "habitat": "kelp"}, "Invalid habitat"),
        ({"geometry": POLYGON, "habitat": "warm-water-corals"}, "Invalid habitat"),
        ({"geometry": POLYGON, "habitat": "coldwatercorals"}, "Invalid habitat"),
        ({"geometry": POLYGON, "habitat": "forest"}, "Invalid habitat"),
    ],
    ids=[
        "missing-geometry",
        "empty-geometry",
        "unknown-habitat",
        "habitat-not-loaded",
        "renamed-habitat",
        "single-terrestrial-habitat",
    ],
)
def test_an_unusable_body_is_a_400_naming_the_cause(api: RouteTestClient, body: dict, message: str):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_marine_habitat_maps_to_a_table():
    for habitat in MARINE_HABITATS:
        assert isinstance(habitat.table, AnalysisTable)
