"""Route-level checks for POST /terrestrial-habitats."""

import pytest

from src.analysis import TERRESTRIAL_HABITAT_CLASSES
from tests.routes.helpers import ENGINE, HABITATS_STATS, POLYGON, RouteTestClient

PATH = "/terrestrial-habitats"


# --- the happy path ----------------------------------------------------------------


def test_returns_habitats_stats(api: RouteTestClient):
    response = api.client.post(PATH, json={"geometry": POLYGON})

    assert response.status_code == 200
    assert response.json() == HABITATS_STATS


def test_queries_with_the_default_terrestrial_table_and_classes(api: RouteTestClient):
    api.client.post(PATH, json={"geometry": POLYGON})

    assert api.calls == [(ENGINE, POLYGON)]


def test_the_geometry_is_passed_through_untouched(api: RouteTestClient):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature})

    _, geometry = api.calls[0]
    assert geometry == feature


def test_other_is_not_reported():
    """The progress tracker leaves "Other" out, so the two would not add up."""
    assert 255 not in TERRESTRIAL_HABITAT_CLASSES


# --- rejections --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "Geometry is required"),
        ({"geometry": {}}, "Geometry is required"),
        ({"geometry": "not-geojson"}, "Invalid geometry: expected a GeoJSON object"),
    ],
    ids=["missing-geometry", "empty-geometry", "not-an-object"],
)
def test_an_unusable_body_is_a_400_naming_the_cause(api: RouteTestClient, body: dict, message: str):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []
