import pytest
from pydantic import ValidationError

from src.analysis import AnalysisTable, serialize_response
from src.schemas import AnalysisRequest, AnalysisResponse, Environment, LocationStats, Stat

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


def test_stats_defaults_to_empty():
    assert AnalysisRequest(geometry=POLYGON).stats == []


def test_stats_accepts_a_list():
    request = AnalysisRequest(geometry=POLYGON, stats=["fully-highly-protected"])

    assert request.stats == ["fully-highly-protected"]


def test_stats_accepts_a_comma_separated_string():
    request = AnalysisRequest(geometry=POLYGON, stats="fully-highly-protected")

    assert request.stats == [Stat.FULLY_HIGHLY_PROTECTED]


def test_an_empty_stats_string_yields_no_stats():
    assert AnalysisRequest(geometry=POLYGON, stats="").stats == []


def test_empty_segments_in_a_comma_string_are_dropped():
    request = AnalysisRequest(geometry=POLYGON, stats="fully-highly-protected,,")

    assert request.stats == [Stat.FULLY_HIGHLY_PROTECTED]


def test_unrecognised_stats_are_rejected():
    """A typo would otherwise return a normal 200 with the stat silently missing."""
    with pytest.raises(ValidationError):
        AnalysisRequest(geometry=POLYGON, stats=["something-new"])


def test_a_comma_string_is_split_before_each_entry_is_validated():
    with pytest.raises(ValidationError) as excinfo:
        AnalysisRequest(geometry=POLYGON, stats="fully-highly-protected,habitat")

    assert [error["loc"] for error in excinfo.value.errors()] == [("stats", 1)]


# --- fully-highly-protected ------------------------------------------


def test_fhp_is_included_for_marine_when_asked_for():
    request = AnalysisRequest(geometry=POLYGON, stats=["fully-highly-protected"])

    assert request.include_fully_highly_protected


def test_fhp_is_skipped_when_not_asked_for():
    assert not AnalysisRequest(geometry=POLYGON).include_fully_highly_protected


def test_fhp_is_skipped_for_terrestrial_even_when_asked_for():
    request = AnalysisRequest(
        geometry=POLYGON, environment="terrestrial", stats=["fully-highly-protected"]
    )

    assert not request.include_fully_highly_protected


# --- AnalysisResponse --------------------------------------------------------------


def test_the_analysis_layer_output_validates():
    rows = [("ESP", 30.0, 100.0), ("PRT", 20.0, 100.0)]

    response = AnalysisResponse.model_validate(serialize_response(rows))

    assert response.total_area == 100.0
    assert response.total_protected_area == 50.0
    assert [area.code for area in response.locations_area] == ["ESP", "PRT"]


def test_an_empty_result_validates():
    response = AnalysisResponse.model_validate(serialize_response([]))

    assert response.locations_area == []
    assert response.total_area == 0


def test_fully_highly_protected_is_absent_by_default():
    response = AnalysisResponse.model_validate(serialize_response([("ESP", 30.0, 100.0)]))

    assert response.fully_highly_protected is None
    assert "fully_highly_protected" not in response.model_dump(exclude_none=True)


def test_fully_highly_protected_survives_serialization():
    payload = serialize_response([("ESP", 30.0, 100.0)])
    payload["fully_highly_protected"] = serialize_response([("ESP", 10.0, 100.0)])

    response = AnalysisResponse.model_validate(payload)

    assert isinstance(response.fully_highly_protected, LocationStats)
    assert response.fully_highly_protected.total_protected_area == 10.0
    assert response.model_dump(exclude_none=True)["fully_highly_protected"] == {
        "locations_area": [{"code": "ESP", "protected_area": 10.0}],
        "total_area": 100.0,
        "total_protected_area": 10.0,
    }
