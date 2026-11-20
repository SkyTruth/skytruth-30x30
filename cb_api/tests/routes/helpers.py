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

# Stands in for the pooled engine
ENGINE = object()


@dataclass
class RouteTestClient:
    """Sends requests to the app and records each call to the analysis function.

    The analysis function is replaced with a fake that returns STATS, so the tests
    don't need a database.
    """

    client: TestClient
    calls: list[tuple[Any, Any, Any]] = field(default_factory=list)
