"""The spatial query in src/analysis.py, against a PostGIS database."""

import pytest
from sqlalchemy import text
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
    assert areas["AAA"] == 2 * areas["BBB"]


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


def test_a_self_intersecting_polygon_is_repaired(analysis_tables: Engine):
    """ST_MakeValid should repair a self-intersecting polygon (bow-tie)."""
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 1], [2, 0], [0, 1], [0, 0]]],
    }

    result = get_locations_stats(analysis_tables, bowtie, AnalysisTable.MARINE)

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


def test_a_topology_error_is_flagged_as_invalid_geometry(analysis_tables: Engine):
    """GEOS refuses to intersect a self-intersecting polygon, so flag as invalid geometry."""
    with analysis_tables.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO data.{AnalysisTable.MARINE.value} (location, the_geom) VALUES "
                "('CCC', ST_Multi(ST_GeomFromText("
                "'POLYGON((10 10, 11 11, 11 10, 10 11, 10 10))', 4326)))"
            )
        )

    with pytest.raises(
        BadRequestError, match="Invalid geometry: input geometry could not be processed"
    ):
        get_locations_stats(analysis_tables, box(10.25, 10.25, 10.75, 10.75), AnalysisTable.MARINE)
