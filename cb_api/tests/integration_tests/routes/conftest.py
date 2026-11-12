from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.main import app, get_engine


@pytest.fixture
def api(analysis_tables: Engine) -> Iterator[TestClient]:
    """A client whose requests reach the test database."""
    app.dependency_overrides[get_engine] = lambda: analysis_tables
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
