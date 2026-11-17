"""Each route reads its own table, through the app and a PostGIS database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.analysis import AnalysisTable
from src.main import app, get_engine
from tests.integration_tests.helpers import MAX_DEGREE_CELL_KM2, MIN_DEGREE_CELL_KM2, box

pytestmark = pytest.mark.integration

# Each table has a row over this box whose location is the table's name
TABLE_NAME_BOX = box(10, 0, 11, 1)

# The rest of the request body, and the table it should read, for each route
ROUTES = {
    "coverage, marine by default": ("/coverage", {}, AnalysisTable.MARINE),
    "coverage, terrestrial": (
        "/coverage",
        {"environment": "terrestrial"},
        AnalysisTable.TERRESTRIAL,
    ),
    "protection-level": ("/protection-level", {}, AnalysisTable.FULLY_HIGHLY_PROTECTED),
}


@pytest.fixture
def client(analysis_tables: Engine) -> Iterator[TestClient]:
    app.dependency_overrides[get_engine] = lambda: analysis_tables
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(("path", "body", "table"), ROUTES.values(), ids=ROUTES)
def test_each_route_reads_its_own_table(
    client: TestClient, path: str, body: dict, table: AnalysisTable
):
    response = client.post(path, json={"geometry": TABLE_NAME_BOX, **body})

    assert response.status_code == 200
    [location] = response.json()["locations"]
    assert location["code"] == table.value
    assert MIN_DEGREE_CELL_KM2 < location["added_area"] < MAX_DEGREE_CELL_KM2
