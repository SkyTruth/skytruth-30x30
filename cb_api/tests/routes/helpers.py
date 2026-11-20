"""Shared test data and client for the route tests."""

from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

# The results every route gets back, in place of a real analysis
STATS = {
    "locations": [{"code": "ESP", "added_area": 30.0}],
    "total_area": 100.0,
}

# The results the raster habitats query gets back
HABITATS_STATS = {
    "locations": [
        {
            "code": "ESP",
            "habitats": [
                {"habitat": "forest", "added_area": 30.0},
                {"habitat": "desert", "added_area": 5.0},
            ],
        },
    ],
    "total_area": 100.0,
}

# Stands in for the pooled engine
ENGINE = object()


@dataclass
class RouteTestClient:
    """Sends requests to the app and records each call to the analysis functions.

    The analysis functions are replaced with fakes that return STATS or
    HABITATS_STATS, so the tests don't need a database. A call is recorded as
    (engine, geometry, table), or (engine, geometry) for the raster habitats.
    """

    client: TestClient
    calls: list[tuple[Any, ...]] = field(default_factory=list)
