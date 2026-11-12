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
    "locations": [{"code": "ESP", "added_area": 4.0}],
    "total_area": 100.0,
}

ENGINE = object()


@dataclass
class HabitatsTestClient:
    """What each test works with: a client for sending requests to the app, and a record
    of every call the route made to the analysis layer, which is replaced with a stub so
    no database is involved."""

    client: TestClient
    calls: list[tuple[Any, Any, Any]] = field(default_factory=list)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[HabitatsTestClient]:
    test_client = HabitatsTestClient(client=TestClient(app))

    def fake_get_locations_stats(engine: Any, geometry: Any, table: Any) -> dict:
        test_client.calls.append((engine, geometry, table))
        return dict(STATS)

    monkeypatch.setattr(main, "get_locations_stats", fake_get_locations_stats)
    app.dependency_overrides[get_engine] = lambda: ENGINE
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


# --- the happy path ----------------------------------------------------------------


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_returns_location_stats(api: HabitatsTestClient, habitat: Habitat):
    response = api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    assert response.status_code == 200
    assert response.json() == STATS


@pytest.mark.parametrize("habitat", list(Habitat))
def test_each_habitat_reads_its_own_table(api: HabitatsTestClient, habitat: Habitat):
    api.client.post(PATH, json={"geometry": POLYGON, "habitat": habitat.value})

    _, _, table = api.calls[0]
    assert table is habitat.table


def test_the_habitats_read_distinct_tables():
    """A copy-paste slip in the enum would quietly serve one habitat's numbers
    for another."""
    tables = {habitat.table for habitat in Habitat}

    assert len(tables) == len(list(Habitat))


def test_the_geometry_is_passed_through_untouched(api: HabitatsTestClient):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(PATH, json={"geometry": feature, "habitat": "mangroves"})

    _, geometry, _ = api.calls[0]
    assert geometry == feature


# --- rejections --------------------------------------------------------------------


def test_the_habitat_is_required(api: HabitatsTestClient):
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
def test_an_unusable_body_is_a_400_naming_the_cause(
    api: HabitatsTestClient, body: dict, message: str
):
    response = api.client.post(PATH, json=body)

    assert response.status_code == 400
    assert response.json() == {"error": message}
    assert api.calls == []


# --- the enum ----------------------------------------------------------------------


def test_every_habitat_maps_to_a_table():
    for habitat in Habitat:
        assert isinstance(habitat.table, AnalysisTable)
