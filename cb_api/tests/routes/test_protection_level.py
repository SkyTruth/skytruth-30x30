"""Route-level checks for POST /protection-level."""

import pytest

from src.schemas import ProtectionLevel
from src.services.vector import AnalysisTable
from tests.routes.helpers import POLYGON, STATS, RouteTestClient

PATH = "/protection-level"


# --- the happy path ----------------------------------------------------------------


def test_a_geometry_returns_location_stats(api: RouteTestClient):
    response = api.client.post(PATH, json={"geometry": POLYGON})

    assert response.status_code == 200
    assert response.json() == STATS


def test_the_level_defaults_to_fully_highly_protected(api: RouteTestClient):
    api.client.post(PATH, json={"geometry": POLYGON})

    _, _, table = api.calls[0]
    assert table is AnalysisTable.FULLY_HIGHLY_PROTECTED


def test_an_explicit_level_reads_the_same_table(api: RouteTestClient):
    api.client.post(PATH, json={"geometry": POLYGON, "level": "fully-highly-protected"})

    _, _, table = api.calls[0]
    assert table is AnalysisTable.FULLY_HIGHLY_PROTECTED


def test_marine_is_accepted_explicitly(api: RouteTestClient):
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "marine"})

    assert response.status_code == 200


def test_the_geometry_is_passed_through_untouched(api: RouteTestClient):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature})

    _, geometry, _ = api.calls[0]
    assert geometry == feature


# --- marine only -------------------------------------------------------------------


def test_terrestrial_is_refused(api: RouteTestClient):
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    assert response.status_code == 400
    assert api.calls == []


def test_the_refusal_names_the_level_and_the_environment(api: RouteTestClient):
    """A bare "marine only" would not survive a second level or a terrestrial table."""
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    error = response.json()["error"]
    assert "fully-highly-protected" in error
    assert "terrestrial" in error


def test_the_refusal_is_not_mistaken_for_a_geometry_problem(api: RouteTestClient):
    """The frontend treats "Invalid geometry" as a drawing the user must redraw."""
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    assert "Invalid geometry" not in response.json()["error"]


def test_the_refusal_is_not_the_generic_validation_body(api: RouteTestClient):
    """A model validator would answer "Invalid request body" and lose the detail."""
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    assert response.json() != {"error": "Invalid request body"}


# --- rejections --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "Geometry is required"),
        ({"geometry": {}}, "Geometry is required"),
        (
            {"geometry": POLYGON, "environment": "lunar"},
            "Environment must be one of `marine` or `terrestrial`",
        ),
        ({"geometry": POLYGON, "level": "barely-protected"}, "Invalid level"),
    ],
    ids=["missing-geometry", "empty-geometry", "unknown-environment", "unknown-level"],
)
def test_an_unusable_body_is_a_400_naming_the_cause(api: RouteTestClient, body: dict, message: str):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_level_maps_to_a_table():
    for level in ProtectionLevel:
        assert isinstance(level.table, AnalysisTable)
