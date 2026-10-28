"""Route-level checks for POST /coverage and its POST / alias."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import main
from src.analysis import AnalysisTable
from src.errors import BadRequestError
from src.main import app, get_engine

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

PATHS = ["/coverage", "/"]

STATS = {
    "locations_area": [{"code": "ESP", "protected_area": 30.0}],
    "total_area": 100.0,
    "total_protected_area": 30.0,
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


@pytest.mark.parametrize("path", PATHS)
def test_a_geometry_returns_location_stats(api: Harness, path: str):
    response = api.client.post(path, json={"geometry": POLYGON})

    assert response.status_code == 200
    assert response.json() == STATS


def test_both_paths_answer_identically(api: Harness):
    bodies = [
        api.client.post(path, json={"geometry": POLYGON, "environment": "terrestrial"}).json()
        for path in PATHS
    ]

    assert bodies[0] == bodies[1]
    assert api.calls[0] == api.calls[1]


@pytest.mark.parametrize("path", PATHS)
def test_the_pooled_engine_is_handed_to_the_analysis(api: Harness, path: str):
    api.client.post(path, json={"geometry": POLYGON})

    engine, _, _ = api.calls[0]
    assert engine is ENGINE


@pytest.mark.parametrize("path", PATHS)
def test_the_geometry_is_passed_through_untouched(api: Harness, path: str):
    feature = {"type": "Feature", "geometry": POLYGON, "properties": {}}

    api.client.post(path, json={"geometry": feature})

    _, geometry, _ = api.calls[0]
    assert geometry == feature


# --- environment to table ----------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "table"),
    [
        ({"geometry": POLYGON}, AnalysisTable.MARINE),
        ({"geometry": POLYGON, "environment": "marine"}, AnalysisTable.MARINE),
        ({"geometry": POLYGON, "environment": "terrestrial"}, AnalysisTable.TERRESTRIAL),
    ],
)
def test_the_environment_chooses_the_table(api: Harness, body: dict, table: AnalysisTable):
    api.client.post("/coverage", json=body)

    _, _, chosen = api.calls[0]
    assert chosen is table


# --- the response shape ------------------------------------------------------------


def test_extra_keys_from_the_analysis_layer_do_not_reach_the_caller(
    api: Harness, monkeypatch: pytest.MonkeyPatch
):
    """response_model is what guarantees the body, not the analysis layer."""
    monkeypatch.setattr(main, "get_locations_stats", lambda *_: {**STATS, "debug": "leak"})

    response = api.client.post("/coverage", json={"geometry": POLYGON})

    assert response.status_code == 200
    assert "debug" not in response.json()


def test_unknown_request_fields_are_ignored(api: Harness):
    """`stats` is no longer an input, and sending it is not an error."""
    response = api.client.post(
        "/coverage", json={"geometry": POLYGON, "stats": "fully-highly-protected"}
    )

    assert response.status_code == 200
    assert response.json() == STATS


# --- rejections --------------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS)
def test_a_missing_geometry_is_a_400(api: Harness, path: str):
    response = api.client.post(path, json={})

    assert response.status_code == 400
    assert response.json() == {"error": "Geometry is required"}
    assert api.calls == []


@pytest.mark.parametrize("path", PATHS)
def test_an_unknown_environment_is_a_400(api: Harness, path: str):
    response = api.client.post(path, json={"geometry": POLYGON, "environment": "lunar"})

    assert response.status_code == 400
    assert response.json() == {"error": "Environment must be one of `marine` or `terrestrial`"}
    assert api.calls == []


@pytest.mark.parametrize("path", PATHS)
def test_a_rejected_geometry_keeps_its_message(
    api: Harness, monkeypatch: pytest.MonkeyPatch, path: str
):
    """The frontend matches on 'Invalid geometry', so the text has to survive."""

    def reject(*_: Any) -> dict:
        raise BadRequestError("Invalid geometry: input geometry is empty")

    monkeypatch.setattr(main, "get_locations_stats", reject)

    response = api.client.post(path, json={"geometry": POLYGON})

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid geometry: input geometry is empty"}


# --- the schema --------------------------------------------------------------------


def test_the_alias_is_marked_deprecated_and_coverage_is_not():
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert paths["/"]["post"].get("deprecated") is True
    assert paths["/coverage"]["post"].get("deprecated") is not True
