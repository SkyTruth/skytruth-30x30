"""End-to-end checks of the spatial query against a PostGIS database.
"""

import pytest
from sqlalchemy.engine import Engine

from src.analysis import AnalysisTable, get_locations_stats

pytestmark = pytest.mark.integration

MIN_DEGREE_CELL_KM2 = 11_000
MAX_DEGREE_CELL_KM2 = 14_000


def box(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def by_code(result: dict) -> dict[str, float]:
    return {area["code"]: area["protected_area"] for area in result["locations_area"]}


def test_areas_are_square_kilometres(analysis_tables: Engine):
    """A wrong projection or a missing /1e6 would be out by orders of magnitude."""
    result = get_locations_stats(analysis_tables, box(1, 0, 2, 1), AnalysisTable.MARINE)

    assert MIN_DEGREE_CELL_KM2 < result["total_area"] < MAX_DEGREE_CELL_KM2


def test_rows_sharing_a_location_are_summed_by_the_query(analysis_tables: Engine):
    """AAA is two separate boxes the same size as the single BBB box."""
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable.MARINE)

    areas = by_code(result)
    assert sorted(areas) == ["AAA", "BBB"]
    assert areas["AAA"] == 2 * areas["BBB"]


def test_total_protected_area_is_the_sum_of_the_locations(analysis_tables: Engine):
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable.MARINE)

    assert result["total_protected_area"] == sum(by_code(result).values())


def test_a_fully_covered_area_is_entirely_protected(analysis_tables: Engine):
    """The boxes tile the request exactly, so protected and total should agree."""
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable.MARINE)

    assert result["total_protected_area"] == pytest.approx(result["total_area"], abs=2)


def test_only_the_overlapping_part_is_counted(analysis_tables: Engine):
    """Requesting half of the AAA box should return about half its area."""
    whole = get_locations_stats(analysis_tables, box(0, 0, 1, 1), AnalysisTable.MARINE)
    half = get_locations_stats(analysis_tables, box(0, 0, 0.5, 1), AnalysisTable.MARINE)

    assert half["locations_area"][0]["protected_area"] == pytest.approx(
        whole["locations_area"][0]["protected_area"] / 2, rel=0.01
    )


def test_an_area_touching_nothing_comes_back_empty(analysis_tables: Engine):
    result = get_locations_stats(analysis_tables, box(50, 50, 51, 51), AnalysisTable.MARINE)

    assert result == {"locations_area": [], "total_area": 0, "total_protected_area": 0}


@pytest.mark.parametrize("table", list(AnalysisTable))
def test_every_table_in_the_enum_exists(analysis_tables: Engine, table: AnalysisTable):
    """A typo in the enum would only ever show up against a real schema."""
    result = get_locations_stats(analysis_tables, box(0, 0, 3, 1), AnalysisTable(table))

    assert result["total_protected_area"] > 0


def test_a_self_intersecting_polygon_is_repaired(analysis_tables: Engine):
    """ST_MakeValid should repair a self-intersecting polygon (bow-tie)."""
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 1], [2, 0], [0, 1], [0, 0]]],
    }

    result = get_locations_stats(analysis_tables, bowtie, AnalysisTable.MARINE)

    assert result["total_protected_area"] > 0


# --- geometries PostGIS has to reject ---------------------------------------


def test_a_line_is_rejected(analysis_tables: Engine):
    line = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}

    with pytest.raises(ValueError, match="must be a Polygon or MultiPolygon"):
        get_locations_stats(analysis_tables, line, AnalysisTable.MARINE)


def test_an_empty_polygon_is_rejected(analysis_tables: Engine):
    with pytest.raises(ValueError, match="Input geometry is empty"):
        get_locations_stats(
            analysis_tables, {"type": "Polygon", "coordinates": []}, AnalysisTable.MARINE
        )


def test_unparseable_geojson_is_rejected(analysis_tables: Engine):
    with pytest.raises(ValueError, match="Unable to parse input geometry"):
        get_locations_stats(analysis_tables, {"type": "Nonsense"}, AnalysisTable.MARINE)
