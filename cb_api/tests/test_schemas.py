import pytest
from pydantic import ValidationError

from src.analysis import AnalysisTable, serialize_response
from src.schemas import AnalysisRequest, Environment, LocationStats

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}


# --- Environment -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("environment", "table"),
    [
        (Environment.MARINE, AnalysisTable.MARINE),
        (Environment.TERRESTRIAL, AnalysisTable.TERRESTRIAL),
    ],
)
def test_each_environment_maps_to_its_table(environment: Environment, table: AnalysisTable):
    assert environment.table is table


# --- AnalysisRequest ---------------------------------------------------------------


def test_geometry_is_required():
    with pytest.raises(ValidationError) as excinfo:
        AnalysisRequest()

    assert [error["loc"] for error in excinfo.value.errors()] == [("geometry",)]


def test_geometry_passes_through_untouched():
    assert AnalysisRequest(geometry=POLYGON).geometry == POLYGON


def test_environment_defaults_to_marine():
    assert AnalysisRequest(geometry=POLYGON).environment is Environment.MARINE


def test_environment_accepts_terrestrial():
    request = AnalysisRequest(geometry=POLYGON, environment="terrestrial")

    assert request.environment is Environment.TERRESTRIAL


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest(geometry=POLYGON, environment="lunar")


def test_unknown_fields_are_ignored():
    """`stats` is no longer an input. A caller still sending it gets a normal result
    rather than a rejection, which is what the field's absence should mean."""
    request = AnalysisRequest(geometry=POLYGON, stats="fully-highly-protected")

    assert not hasattr(request, "stats")
    assert request.geometry == POLYGON


# --- LocationStats -----------------------------------------------------------------


def test_the_analysis_layer_output_validates():
    rows = [
        {"location": "ESP", "portion_area_km2": 30.0, "user_area_km2": 100.0},
        {"location": "PRT", "portion_area_km2": 20.0, "user_area_km2": 100.0},
    ]

    response = LocationStats.model_validate(serialize_response(rows))

    assert response.total_area == 100.0
    assert response.total_protected_area == 50.0
    assert [area.code for area in response.locations_area] == ["ESP", "PRT"]


def test_an_empty_result_validates():
    response = LocationStats.model_validate(serialize_response([]))

    assert response.locations_area == []
    assert response.total_area == 0
