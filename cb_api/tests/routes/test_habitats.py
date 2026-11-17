"""Route-level checks for POST /habitats."""

import pytest

from src.analysis import AnalysisTable
from src.schemas import Habitat
from tests.routes.helpers import POLYGON, STATS, RouteTestClient

PATH = "/habitats"


# --- the happy path ----------------------------------------------------------------


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_returns_location_stats(api: RouteTestClient, habitat: Habitat):
    response = api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    assert response.status_code == 200
    assert response.json() == STATS


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_reads_its_own_table(api: RouteTestClient, habitat: Habitat):
    api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    _, _, table = api.calls[0]
    assert table is habitat.table


def test_the_habitats_read_distinct_tables():
    """A copy-paste slip in the enum would quietly serve one habitat's numbers
    for another."""
    tables = {habitat.table for habitat in Habitat}

    assert len(tables) == len(list(Habitat))


def test_the_geometry_is_passed_through_untouched(api: RouteTestClient):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature, "habitat": "mangroves"})

    _, geometry, _ = api.calls[0]
    assert geometry == feature


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
    ],
    ids=[
        "missing-geometry",
        "empty-geometry",
        "unknown-habitat",
        "habitat-not-loaded",
        "renamed-habitat",
    ],
)
def test_an_unusable_body_is_a_400_naming_the_cause(api: RouteTestClient, body: dict, message: str):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_habitat_maps_to_a_table():
    for habitat in Habitat:
        assert isinstance(habitat.table, AnalysisTable)
