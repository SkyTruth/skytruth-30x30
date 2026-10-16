"""Route-level checks for POST /habitats."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import main
from src.analysis import AnalysisTable
from src.main import app, get_engine
from src.schemas import Habitat

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

PATH = "/habitats"

STATS = {
    "locations_area": [{"code": "ESP", "protected_area": 4.0}],
    "total_area": 100.0,
    "total_protected_area": 4.0,
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


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_returns_location_stats(api: Harness, habitat: Habitat):
    response = api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    assert response.status_code == 200
    assert response.json() == STATS


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_reads_its_own_table(api: Harness, habitat: Habitat):
    api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    _, _, table = api.calls[0]
    assert table is habitat.table


def test_the_habitats_read_four_distinct_tables(api: Harness):
    """A copy-paste slip in the enum would quietly serve one habitat's numbers
    for another."""
    tables = {habitat.table for habitat in Habitat}

    assert len(tables) == len(list(Habitat))


def test_the_pooled_engine_and_geometry_are_passed_through(api: Harness):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature, "habitat": "mangroves"})

    engine, geometry, _ = api.calls[0]
    assert engine is ENGINE
    assert geometry == feature


# --- rejections --------------------------------------------------------------------


def test_the_habitat_is_required(api: Harness):
    """Unlike `level`, there is no sensible default habitat."""
    response = api.client.post(PATH, json={"geometry": POLYGON})

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid request body"}
    assert api.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"habitat": "mangroves"},
        {"geometry": POLYGON, "habitat": "kelp"},
        {"geometry": POLYGON, "habitat": "seamounts"},
    ],
)
def test_an_unusable_body_is_a_400(api: Harness, body: dict):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid request body"}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_habitat_maps_to_a_table():
    for habitat in Habitat:
        assert isinstance(habitat.table, AnalysisTable)
