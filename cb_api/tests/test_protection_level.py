"""Route-level checks for POST /protection-level."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import main
from src.analysis import AnalysisTable
from src.main import app, get_engine
from src.schemas import ProtectionLevel

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

PATH = "/protection-level"

STATS = {
    "locations_area": [{"code": "ESP", "protected_area": 12.0}],
    "total_area": 100.0,
    "total_protected_area": 12.0,
}

ENGINE = object()


@dataclass
class Harness:
    client: TestClient
    calls: list[tuple[Any, Any, Any]] = field(default_factory=list)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    harness = Harness(client=TestClient(app))

    def fake_get_locations_stats(engine: Any, geometry: Any, table: Any) -> dict:
        harness.calls.append((engine, geometry, table))
        return dict(STATS)

    monkeypatch.setattr(main, "get_locations_stats", fake_get_locations_stats)
    app.dependency_overrides[get_engine] = lambda: ENGINE
    try:
        yield harness
    finally:
        app.dependency_overrides.clear()


# --- the happy path ----------------------------------------------------------------


def test_a_geometry_returns_location_stats(api: Harness):
    response = api.client.post(PATH, json={"geometry": POLYGON})

    assert response.status_code == 200
    assert response.json() == STATS


def test_the_level_defaults_to_fully_highly_protected(api: Harness):
    api.client.post(PATH, json={"geometry": POLYGON})

    _, _, table = api.calls[0]
    assert table is AnalysisTable.FULLY_HIGHLY_PROTECTED


def test_an_explicit_level_reads_the_same_table(api: Harness):
    api.client.post(PATH, json={"geometry": POLYGON, "level": "fully-highly-protected"})

    _, _, table = api.calls[0]
    assert table is AnalysisTable.FULLY_HIGHLY_PROTECTED


def test_marine_is_accepted_explicitly(api: Harness):
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "marine"})

    assert response.status_code == 200


def test_the_pooled_engine_and_geometry_are_passed_through(api: Harness):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature})

    engine, geometry, _ = api.calls[0]
    assert engine is ENGINE
    assert geometry == feature


# --- marine only -------------------------------------------------------------------


def test_terrestrial_is_refused(api: Harness):
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    assert response.status_code == 400
    assert api.calls == []


def test_the_refusal_names_the_level_and_the_environment(api: Harness):
    """A bare "marine only" would not survive a second level or a terrestrial table."""
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    error = response.json()["error"]
    assert "fully-highly-protected" in error
    assert "terrestrial" in error


def test_the_refusal_is_not_mistaken_for_a_geometry_problem(api: Harness):
    """The frontend treats "Invalid geometry" as a drawing the user must redraw."""
    response = api.client.post(PATH, json={"geometry": POLYGON, "environment": "terrestrial"})

    assert "Invalid geometry" not in response.json()["error"]


def test_the_refusal_is_not_the_generic_validation_body(api: Harness):
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
def test_an_unusable_body_is_a_400_naming_the_cause(api: Harness, body: dict, message: str):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_level_maps_to_a_table():
    for level in ProtectionLevel:
        assert isinstance(level.table, AnalysisTable)
