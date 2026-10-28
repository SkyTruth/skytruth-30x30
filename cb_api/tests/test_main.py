from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.config import get_settings
from src.errors import BadRequestError
from src.main import app, get_engine
from src.schemas import AnalysisRequest

client = TestClient(app)


@app.get("/_test/bad-request", include_in_schema=False)
def _raise_bad_request():
    raise BadRequestError("Invalid geometry: input geometry is empty")


@app.get("/_test/value-error", include_in_schema=False)
def _raise_value_error():
    raise ValueError("invalid literal for int() with base 10: 's3cret'")


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


def test_bad_request_error_becomes_a_400_with_its_message():
    response = client.get("/_test/bad-request")

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid geometry: input geometry is empty"}


def test_a_plain_value_error_is_a_server_error(caplog: pytest.LogCaptureFixture):
    response = error_client.get("/_test/value-error")

    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert "s3cret" in caplog.text


def test_unexpected_errors_become_a_500_without_the_message(caplog: pytest.LogCaptureFixture):
    response = error_client.get("/_test/boom")

    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert "connection reset" in caplog.text


GEOMETRY_REQUIRED = {"error": "Geometry is required"}
ENVIRONMENT_INVALID = {"error": "Environment must be one of `marine` or `terrestrial`"}


def test_validation_failures_are_400_not_422():
    """FastAPI's default is 422 with {"detail": [...]}, which the frontend cannot read."""
    response = client.post("/_test/validate", json={"geometry": POLYGON, "environment": "lunar"})

    assert response.status_code == 400
    assert "detail" not in response.json()


@pytest.mark.parametrize(
    "body",
    [{}, {"geometry": None}, {"geometry": {}}],
    ids=["missing", "null", "empty"],
)
def test_an_absent_geometry_is_reported_as_required(body: dict):
    response = client.post("/_test/validate", json=body)

    assert response.status_code == 400
    assert response.json() == GEOMETRY_REQUIRED


@pytest.mark.parametrize("environment", ["lunar", None, "Marine"])
def test_an_unknown_environment_names_the_allowed_values(environment):
    response = client.post(
        "/_test/validate", json={"geometry": POLYGON, "environment": environment}
    )

    assert response.status_code == 400
    assert response.json() == ENVIRONMENT_INVALID


def test_geometry_is_reported_before_environment():
    response = client.post("/_test/validate", json={"environment": "lunar"})

    assert response.json() == GEOMETRY_REQUIRED


@pytest.mark.parametrize("geometry", ["not a geometry", [1, 2], 3])
def test_a_geometry_of_the_wrong_type_is_an_invalid_geometry(geometry):
    response = client.post("/_test/validate", json={"geometry": geometry})

    assert response.status_code == 400
    assert response.json() == {"error": "Invalid geometry: expected a GeoJSON object"}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ('{"geometry":', "Request body is not valid JSON"),
        ("[1, 2]", "Request body must be a JSON object"),
        ("", "Request body must be a JSON object"),
    ],
    ids=["malformed", "array", "empty"],
)
def test_a_body_problem_names_the_body(raw: str, message: str):
    response = client.post(
        "/_test/validate", content=raw, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json() == {"error": message}


@pytest.mark.parametrize(
    "raw",
    ['{"geometry":', "[1, 2]", "", '{"environment": "lunar", "geometry": {"type": "Polygon"}}'],
)
def test_only_geometry_problems_say_invalid_geometry(raw: str):
    """The frontend treats "Invalid geometry" as "redraw the shape"."""
    response = client.post(
        "/_test/validate", content=raw, headers={"Content-Type": "application/json"}
    )

    assert "Invalid geometry" not in response.json()["error"]


def test_an_unrecognised_field_error_names_the_field():
    from src.errors import describe_validation_error

    assert describe_validation_error([{"type": "missing", "loc": ("body", "habitat")}]) == (
        "Habitat is required"
    )
    assert describe_validation_error([{"type": "enum", "loc": ("body", "habitat")}]) == (
        "Invalid habitat"
    )


def test_validation_detail_is_logged_but_not_returned(caplog: pytest.LogCaptureFixture):
    response = client.post("/_test/validate", json={"geometry": "not a geometry"})

    assert "dict_type" not in response.text
    assert "dict_type" in caplog.text


# --- CORS --------------------------------------------------------------------------


ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://30x30-dev.skytruth.org",
    "https://30x30.skytruth.org",
]


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_the_post_preflight_is_allowed(origin: str):
    """Browsers send an OPTIONS request before a JSON POST to ask
    permission for the method and header."""
    response = client.options(
        "/_test/validate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["access-control-max-age"] == "3600"


def test_a_preflight_from_an_unknown_origin_is_refused():
    response = client.options(
        "/_test/validate",
        headers={"Origin": "https://example.org", "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_responses_carry_an_allowed_origin(origin: str):
    response = client.get("/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


def test_responses_to_an_unknown_origin_carry_no_allow_origin():
    response = client.get("/health", headers={"Origin": "https://example.org"})

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_server_errors_carry_an_allowed_origin(origin: str):
    """The 500 handler runs outside CORSMiddleware, so it sets the header itself."""
    response = error_client.get("/_test/boom", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["vary"] == "Origin"


def test_server_errors_to_an_unknown_origin_carry_no_allow_origin():
    response = error_client.get("/_test/boom", headers={"Origin": "https://example.org"})

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers
