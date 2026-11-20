"""The spatial query in src/analysis.py, against a PostGIS database."""

import pytest
from sqlalchemy.engine import Engine

from src.analysis import AnalysisTable, get_locations_stats
from src.errors import BadRequestError
from tests.integration_tests.helpers import (
    MAX_DEGREE_CELL_AT_50N_KM2,
    MAX_DEGREE_CELL_KM2,
    MIN_DEGREE_CELL_AT_50N_KM2,
    MIN_DEGREE_CELL_KM2,
    box,
    by_code,
)

pytestmark = pytest.mark.integration


def test_areas_are_square_kilometers(analysis_tables: Engine):
    """A wrong projection or a missing /1e6 would be out by orders of magnitude."""
    result = get_locations_stats(analysis_tables, box(1, 0, 2, 1), AnalysisTable.MARINE)

    assert MIN_DEGREE_CELL_KM2 < result["total_area"] < MAX_DEGREE_CELL_KM2


def test_rows_sharing_a_location_are_summed_by_the_query(analysis_tables: Engine):
    """AAA is two separate boxes the same size as the single BBB box."""
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable.MARINE)

    areas = by_code(result)
    assert sorted(areas) == ["AAA", "BBB"]
    assert areas["AAA"] == pytest.approx(2 * areas["BBB"])


def test_an_area_the_table_covers_completely_is_all_added_area(analysis_tables: Engine):
    """The boxes tile the request exactly, so the locations should add up to the drawn area."""
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable.MARINE)

    assert sum(by_code(result).values()) == pytest.approx(result["total_area"], abs=2)


def test_only_the_overlapping_part_is_counted(analysis_tables: Engine):
    """Requesting half of the AAA box should return about half its area."""
    whole = get_locations_stats(analysis_tables, box(0, 0, 1, 1), AnalysisTable.MARINE)
    half = get_locations_stats(analysis_tables, box(0, 0, 0.5, 1), AnalysisTable.MARINE)

    assert half["locations"][0]["added_area"] == pytest.approx(
        whole["locations"][0]["added_area"] / 2, rel=0.01
    )


def test_an_area_touching_nothing_reports_its_area(analysis_tables: Engine):
    result = get_locations_stats(analysis_tables, box(50, 50, 51, 51), AnalysisTable.MARINE)

    assert result["locations"] == []
    assert MIN_DEGREE_CELL_AT_50N_KM2 < result["total_area"] < MAX_DEGREE_CELL_AT_50N_KM2


def test_a_shape_partly_outside_every_location_lists_only_real_locations(
    analysis_tables: Engine,
):
    """Half of this box lies past the last fixture box. Only shapes touching nothing get
    a row with no location, so the result lists AAA alone and counts the whole box."""
    result = get_locations_stats(analysis_tables, box(2.5, 0, 3.5, 1), AnalysisTable.MARINE)

    assert list(by_code(result)) == ["AAA"]
    assert result["total_area"] == pytest.approx(2 * by_code(result)["AAA"], abs=2)


INVALID_USER_GEOMETRIES = {
    "bow-tie": {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 1], [2, 0], [0, 1], [0, 0]]],
    },
    "ring crossing itself several times": {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [3, 1], [0, 1], [3, 0], [1.5, 1], [1.5, 0], [0, 0.5], [3, 0.5], [0, 0]]
        ],
    },
    "ring touching itself": {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [1, 0.5], [2, 1], [0, 1], [1, 0.5], [0, 0]]],
    },
    "hole crossing the outer ring": {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]],
            [[1.5, 0.2], [2.5, 0.2], [2.5, 0.8], [1.5, 0.8], [1.5, 0.2]],
        ],
    },
    "overlapping parts of a multipolygon": {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]]],
            [[[1, 0], [3, 0], [3, 1], [1, 1], [1, 0]]],
        ],
    },
}


@pytest.mark.parametrize("geometry", INVALID_USER_GEOMETRIES.values(), ids=INVALID_USER_GEOMETRIES)
def test_an_invalid_user_geometry_is_repaired(analysis_tables: Engine, geometry: dict):
    """The query repairs the user's shape before intersecting it, so an invalid shape
    drawn over valid data gets results rather than an error."""
    result = get_locations_stats(analysis_tables, geometry, AnalysisTable.MARINE)

    assert result["total_area"] > 0
    assert sum(by_code(result).values()) > 0


# --- geometries PostGIS has to reject ---------------------------------------


def test_a_line_is_rejected(analysis_tables: Engine):
    line = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}

    with pytest.raises(
        BadRequestError, match="Invalid geometry: input geometry must be a Polygon or MultiPolygon"
    ):
        get_locations_stats(analysis_tables, line, AnalysisTable.MARINE)


def test_an_empty_polygon_is_rejected(analysis_tables: Engine):
    with pytest.raises(BadRequestError, match="Invalid geometry: input geometry is empty"):
        get_locations_stats(
            analysis_tables, {"type": "Polygon", "coordinates": []}, AnalysisTable.MARINE
        )


def test_unparseable_geojson_is_rejected(analysis_tables: Engine):
    with pytest.raises(BadRequestError, match="Invalid geometry: unable to parse input geometry"):
        get_locations_stats(analysis_tables, {"type": "Nonsense"}, AnalysisTable.MARINE)
