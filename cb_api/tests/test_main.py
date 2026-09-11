from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.config import get_settings
from src.main import app, get_engine
from src.schemas import AnalysisRequest

client = TestClient(app)


@app.get("/_test/value-error", include_in_schema=False)
def _raise_value_error():
    raise ValueError("Input geometry is empty")


@app.get("/_test/lookup-error", include_in_schema=False)
def _raise_lookup_error():
    raise LookupError("Unknown analysis table: 'nope'")


@app.get("/_test/boom", include_in_schema=False)
def _raise_unexpected():
    raise RuntimeError("connection reset")


@app.post("/_test/validate", include_in_schema=False)
def _validate(body: AnalysisRequest):
    return {"environment": body.environment}


# Server errors are re-raised by TestClient unless this is switched off
error_client = TestClient(app, raise_server_exceptions=False)

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}


# --- health ------------------------------------------------------------------------


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- engine wiring -----------------------------------------------------------------


def test_get_engine_reads_the_engine_off_app_state():
    engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))

    assert get_engine(request) is engine


def test_lifespan_builds_and_disposes_the_engine(monkeypatch: pytest.MonkeyPatch):
    for key, value in {
        "DATABASE_HOST": "db.example.org",
        "DATABASE_NAME": "skytruth",
        "DATABASE_USERNAME": "analysis",
        "DATABASE_PASSWORD": "s3cret",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    try:
        with TestClient(app):
            assert isinstance(app.state.engine, Engine)
    finally:
        get_settings.cache_clear()


# --- error contract ----------------------------------------------------------------


def test_value_error_becomes_a_400_with_its_message():
    response = client.get("/_test/value-error")

    assert response.status_code == 400
    assert response.json() == {"error": "Input geometry is empty"}


def test_unexpected_errors_become_a_500_with_the_message():
    response = error_client.get("/_test/boom")

    assert response.status_code == 500
    assert response.json() == {"error": "connection reset"}


def test_a_missing_geometry_is_reported_as_required():
    response = client.post("/_test/validate", json={})

    assert response.status_code == 400
    assert response.json() == {"error": "geometry is required"}


def test_validation_failures_are_400_not_422():
    """FastAPI's default is 422 with {"detail": [...]}, which the frontend cannot read."""
    response = client.post("/_test/validate", json={"geometry": POLYGON, "environment": "lunar"})

    assert response.status_code == 400
    assert "environment" in response.json()["error"]


# --- CORS --------------------------------------------------------------------------


def test_the_post_preflight_is_allowed():
    """Browsers send an OPTIONS request before a JSON POST to ask
    permission for the method and header.'"""
    response = client.options(
        "/_test/validate",
        headers={
            "Origin": "https://example.org",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["access-control-max-age"] == "3600"


def test_responses_carry_the_wildcard_origin():
    response = client.get("/health", headers={"Origin": "https://example.org"})

    assert response.headers["access-control-allow-origin"] == "*"


def test_server_errors_carry_the_wildcard_origin():
    """The 500 handler runs outside CORSMiddleware, so it sets the header itself."""
    response = error_client.get("/_test/boom", headers={"Origin": "https://example.org"})

    assert response.headers["access-control-allow-origin"] == "*"
