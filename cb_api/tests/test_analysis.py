import pytest
import sqlalchemy

from src.analysis import (
    AnalysisTable,
    get_geojson,
    get_locations_stats,
    serialize_response,
    validate_geometry_topology,
)
from src.errors import BadRequestError

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}


# --- get_geojson -------------------------------------------------------------------


def test_bare_geometry_is_returned_unchanged():
    assert get_geojson(POLYGON) == POLYGON


def test_feature_is_unwrapped_to_its_geometry():
    feature = {"type": "Feature", "properties": {}, "geometry": POLYGON}

    assert get_geojson(feature) == POLYGON


def test_feature_collection_unwraps_its_first_feature():
    collection = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": POLYGON},
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point"}},
        ],
    }

    assert get_geojson(collection) == POLYGON


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "FeatureCollection", "features": []},
        {"type": "FeatureCollection"},
        {"type": "FeatureCollection", "features": {"type": "Feature"}},
        {"type": "FeatureCollection", "features": ["x"]},
        "not an object",
    ],
)
def test_malformed_wrappers_are_rejected(geojson):
    with pytest.raises(BadRequestError, match="Invalid geometry: unable to parse input geometry"):
        get_geojson(geojson)


# --- serialize_response ------------------------------------------------------------


def test_no_rows_produces_a_zeroed_response():
    assert serialize_response([]) == {
        "locations_area": [],
        "total_area": 0,
        "total_protected_area": 0,
    }


def test_single_row_reports_the_user_area_and_one_location():
    assert serialize_response(
        [{"location": "ESP", "portion_area_km2": 30, "user_area_km2": 100}]
    ) == {
        "total_area": 100,
        "locations_area": [{"code": "ESP", "protected_area": 30}],
        "total_protected_area": 30,
    }


def test_distinct_locations_are_listed_separately():
    result = serialize_response(
        [
            {"location": "ESP", "portion_area_km2": 30, "user_area_km2": 100},
            {"location": "PRT", "portion_area_km2": 20, "user_area_km2": 100},
        ]
    )

    assert result["locations_area"] == [
        {"code": "ESP", "protected_area": 30},
        {"code": "PRT", "protected_area": 20},
    ]
    assert result["total_protected_area"] == 50


def test_repeated_locations_accumulate():
    result = serialize_response(
        [
            {"location": "ESP", "portion_area_km2": 30, "user_area_km2": 100},
            {"location": "ESP", "portion_area_km2": 20, "user_area_km2": 100},
        ]
    )

    assert result["locations_area"] == [{"code": "ESP", "protected_area": 50}]
    assert result["total_protected_area"] == 50


def test_rows_without_a_location_contribute_nothing():
    """A null location is skipped entirely — it adds no entry *and* no protected area."""
    result = serialize_response(
        [
            {"location": "ESP", "portion_area_km2": 30, "user_area_km2": 100},
            {"location": None, "portion_area_km2": 999, "user_area_km2": 100},
        ]
    )

    assert result["locations_area"] == [{"code": "ESP", "protected_area": 30}]
    assert result["total_protected_area"] == 30
    assert result["total_area"] == 100


# --- validate_geometry_topology ----------------------------------------------------


class FakeConnection:
    """Stands in for a Connection, returning one mapping row or raising."""

    def __init__(self, row: dict | None = None, error: Exception | None = None):
        self._row = row
        self._error = error

    def execute(self, statement, parameters=None):
        if self._error is not None:
            raise self._error
        return self

    def mappings(self):
        return self

    def one(self):
        return self._row


@pytest.mark.parametrize("geom_type", ["ST_Polygon", "ST_MultiPolygon"])
def test_polygons_pass_validation(geom_type: str):
    conn = FakeConnection({"geom_type": geom_type, "is_empty": False})

    assert validate_geometry_topology(conn, POLYGON) is None


def test_empty_geometry_is_rejected():
    conn = FakeConnection({"geom_type": "ST_Polygon", "is_empty": True})

    with pytest.raises(BadRequestError, match="Invalid geometry: input geometry is empty"):
        validate_geometry_topology(conn, POLYGON)


def test_non_polygon_geometry_is_rejected():
    conn = FakeConnection({"geom_type": "ST_LineString", "is_empty": False})

    with pytest.raises(
        BadRequestError, match="Invalid geometry: input geometry must be a Polygon or MultiPolygon"
    ):
        validate_geometry_topology(conn, POLYGON)


def test_unparseable_geometry_is_rejected():
    conn = FakeConnection(error=sqlalchemy.exc.ProgrammingError("stmt", None, Exception("bad")))

    with pytest.raises(BadRequestError, match="Invalid geometry: unable to parse input geometry"):
        validate_geometry_topology(conn, POLYGON)


def test_a_lost_connection_during_validation_is_not_blamed_on_the_caller():
    error = sqlalchemy.exc.InterfaceError(
        "stmt", None, Exception("network error"), connection_invalidated=True
    )
    conn = FakeConnection(error=error)

    with pytest.raises(sqlalchemy.exc.InterfaceError):
        validate_geometry_topology(conn, POLYGON)


# --- table name handling -----------------------------------------------------------


class RecordingEngine:
    """An engine whose connection records the SQL it is handed and returns no rows."""

    def __init__(self):
        self.statements: list[str] = []

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append(str(statement))
        return self

    def mappings(self):
        return self

    def one(self):
        return {"geom_type": "ST_Polygon", "is_empty": False}

    def all(self):
        return []


@pytest.mark.parametrize("table", list(AnalysisTable))
def test_every_allowed_table_reaches_the_query(table: AnalysisTable):
    engine = RecordingEngine()

    get_locations_stats(engine, POLYGON, table)

    assert f"data.{table.value}" in engine.statements[1]


def test_plain_string_naming_an_allowed_table_is_accepted():
    engine = RecordingEngine()

    get_locations_stats(engine, POLYGON, "eez_minus_mpa_v2")

    assert "data.eez_minus_mpa_v2" in engine.statements[1]


@pytest.mark.parametrize(
    "table_name",
    [
        "not_a_table",
        "eez_minus_mpa",
        "eez_minus_mpa_v2; DROP TABLE data.eez_minus_mpa_v2--",
        "eez_minus_mpa_v2 UNION SELECT 1,2,3",
        "",
    ],
)
def test_unknown_table_names_never_reach_the_database(table_name: str):
    engine = RecordingEngine()

    with pytest.raises(LookupError):
        get_locations_stats(engine, POLYGON, table_name)

    assert engine.statements == []


# --- database failures -------------------------------------------------------------


class ExplodingEngine(RecordingEngine):
    """Passes topology validation, then raises the given error from the analysis query."""

    def __init__(self, error: Exception):
        super().__init__()
        self._error = error

    def execute(self, statement, parameters=None):
        self.statements.append(str(statement))
        if len(self.statements) > 1:
            raise self._error
        return self


@pytest.mark.parametrize(
    "error",
    [
        sqlalchemy.exc.ProgrammingError("stmt", None, Exception("GEOSIntersection")),
        sqlalchemy.exc.ProgrammingError("stmt", None, Exception("canceling statement")),
        sqlalchemy.exc.InterfaceError("stmt", None, Exception("network error")),
    ],
)
def test_analysis_query_failures_are_not_blamed_on_the_caller(
    error: sqlalchemy.exc.DBAPIError,
):
    """The geometry has already passed validation, so anything the query raises is ours."""
    with pytest.raises(type(error)):
        get_locations_stats(ExplodingEngine(error), POLYGON, AnalysisTable.MARINE)
