from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import main
from src.main import app, get_engine
from tests.routes.helpers import ENGINE, HABITATS_STATS, STATS, RouteTestClient


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[RouteTestClient]:
    test_client = RouteTestClient(client=TestClient(app))

    def fake_get_locations_stats(engine: Any, geometry: Any, table: Any) -> dict:
        test_client.calls.append((engine, geometry, table))
        return dict(STATS)

    def fake_get_raster_habitats_stats(engine: Any, geometry: Any, habitats: Any) -> dict:
        test_client.calls.append((engine, geometry, habitats))
        return dict(HABITATS_STATS)

    monkeypatch.setattr(main, "get_locations_stats", fake_get_locations_stats)
    monkeypatch.setattr(main, "get_raster_habitats_stats", fake_get_raster_habitats_stats)
    app.dependency_overrides[get_engine] = lambda: ENGINE
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
