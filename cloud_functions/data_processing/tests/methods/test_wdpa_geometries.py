import math

import geopandas as gpd
import pytest
from shapely.geometry import MultiPoint, Point

from src.methods.download_and_process.wdpa_geometries import (
    buffer_if_point,
    calculate_radius,
    create_point_buffer,
    process_protected_area_geoms,
    simplify_chunk,
    stream_parquet_chunks,
)

MAB = "UNESCO-MAB Biosphere Reserve"

# Equal-area projection the buffering is done in, so a measured area in m2 is exact.
EQUAL_AREA_CRS = "ESRI:54009"


def _row(geometry, rep_area=100.0, desig_eng="National Park", **extra):
    """A single chunk row, as simplify_chunk's apply hands one to buffer_if_point."""
    return gpd.GeoDataFrame(
        {"REP_AREA": [rep_area], "DESIG_ENG": [desig_eng], **{k: [v] for k, v in extra.items()}},
        geometry=[geometry],
        crs="EPSG:4326",
    )


def _area_km2(gdf):
    return float(gdf.to_crs(EQUAL_AREA_CRS).area.sum() / 1e6)


# ---------------------------------------------------------------------------
# calculate_radius
# ---------------------------------------------------------------------------


def test_radius_gives_a_circle_of_the_representative_area():
    """REP_AREA is km2 and the buffer is applied in metres, so the 1e6 conversion
    is the whole point of the function."""
    radius = calculate_radius(100.0, Point(0, 0))

    assert math.pi * radius**2 == pytest.approx(100.0 * 1e6)


def test_multipoint_area_is_split_evenly_across_its_parts():
    """Each part is buffered to its own share, so the parts together cover REP_AREA
    rather than each covering all of it."""
    parts = MultiPoint([(0, 0), (1, 1), (2, 2), (3, 3)])

    radius = calculate_radius(100.0, parts)

    assert 4 * math.pi * radius**2 == pytest.approx(100.0 * 1e6)
    # Quartering the area halves the radius.
    assert radius == pytest.approx(calculate_radius(100.0, Point(0, 0)) / 2)


# ---------------------------------------------------------------------------
# create_point_buffer
# ---------------------------------------------------------------------------


def test_buffered_point_covers_its_representative_area():
    result = create_point_buffer(_row(Point(10, -20), rep_area=100.0))

    # buffer() approximates the circle with a 64-gon, hence the 1% tolerance.
    assert _area_km2(result) == pytest.approx(100.0, rel=0.01)


def test_buffered_multipoint_parts_sum_to_the_representative_area():
    far_apart = MultiPoint([(0, 0), (20, 20)])

    result = create_point_buffer(_row(far_apart, rep_area=100.0))

    assert _area_km2(result) == pytest.approx(100.0, rel=0.01)


def test_buffering_returns_to_4326():
    """The buffer is computed in an equal-area CRS, but everything downstream and
    the WDPA output files are in longlat."""
    result = create_point_buffer(_row(Point(10, -20)))

    assert result.crs == "EPSG:4326"


# ---------------------------------------------------------------------------
# buffer_if_point
# ---------------------------------------------------------------------------


def test_point_with_an_area_is_buffered():
    row = _row(Point(10, -20), rep_area=100.0).iloc[0]

    result = buffer_if_point(row, "EPSG:4326")

    assert result.geom_type == "Polygon"


def test_mab_reserve_point_is_left_unbuffered():
    """MAB reported areas are unreliable, so these points stay points and are
    filtered out of the statistics later rather than being given a fake extent."""
    row = _row(Point(10, -20), rep_area=100.0, desig_eng=MAB).iloc[0]

    result = buffer_if_point(row, "EPSG:4326")

    assert result == Point(10, -20)


def test_point_without_an_area_is_left_alone():
    row = _row(Point(10, -20), rep_area=0.0).iloc[0]

    result = buffer_if_point(row, "EPSG:4326")

    assert result == Point(10, -20)


def test_polygon_is_returned_untouched():
    """Only points get a synthetic extent; a PA that already has a boundary keeps it."""
    polygon = Point(10, -20).buffer(1.0)
    row = _row(polygon, rep_area=100.0).iloc[0]

    result = buffer_if_point(row, "EPSG:4326")

    assert result.equals(polygon)


# ---------------------------------------------------------------------------
# simplify_chunk
# ---------------------------------------------------------------------------


def test_chunk_gets_a_bbox_and_an_area_column():
    chunk = _row(Point(10, -20).buffer(1.0), rep_area=100.0, GIS_AREA=250.0)

    result = simplify_chunk(chunk, tolerance=0.1)

    assert result["bbox"].iloc[0] == pytest.approx((9.0, -21.0, 11.0, -19.0))
    # choose_pa_area prefers GIS_AREA where it is positive.
    assert result["calculated_area_km2"].iloc[0] == pytest.approx(250.0)


def test_simplify_drops_vertices_at_the_given_tolerance():
    circle = Point(0, 0).buffer(1.0)
    chunk = _row(circle, rep_area=100.0)

    result = simplify_chunk(chunk, tolerance=0.5)

    assert len(result.geometry.iloc[0].exterior.coords) < len(circle.exterior.coords)


def test_points_in_a_chunk_are_buffered_on_the_way_through():
    chunk = _row(Point(10, -20), rep_area=100.0)

    result = simplify_chunk(chunk, tolerance=0.0001)

    assert result.geometry.iloc[0].geom_type == "Polygon"


def test_a_broken_chunk_returns_none_rather_than_raising():
    """process_all_files filters None out of its results, so a chunk that cannot be
    processed costs its own rows and nothing else."""
    missing_columns = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")

    assert simplify_chunk(missing_columns, tolerance=0.1) is None


# ---------------------------------------------------------------------------
# stream_parquet_chunks
# ---------------------------------------------------------------------------


@pytest.fixture
def pa_parquet(tmp_path):
    """Five PA rows written as geopandas writes them, i.e. geometry as WKB."""
    path = tmp_path / "pas.parquet"
    gpd.GeoDataFrame(
        {"REP_AREA": [1.0, 2.0, 3.0, 4.0, 5.0]},
        geometry=[Point(x, x) for x in range(5)],
        crs="EPSG:4326",
    ).to_parquet(path)
    return str(path)


def test_rows_arrive_in_batches_of_the_requested_size(pa_parquet):
    chunks = list(stream_parquet_chunks([pa_parquet], batch_size=2))

    assert [len(chunk) for chunk in chunks] == [2, 2, 1]


def test_chunks_come_back_as_geodataframes_in_4326(pa_parquet):
    chunk = next(stream_parquet_chunks([pa_parquet], batch_size=5))

    assert isinstance(chunk, gpd.GeoDataFrame)
    assert chunk.crs == "EPSG:4326"
    assert chunk.geometry.iloc[0] == Point(0, 0)


def test_an_unreadable_file_is_skipped_not_fatal(tmp_path, pa_parquet):
    """One corrupt shapefile in the WDPA archive should cost that file's rows, not
    the whole run."""
    corrupt = tmp_path / "corrupt.parquet"
    corrupt.write_bytes(b"not a parquet file")

    chunks = list(stream_parquet_chunks([str(corrupt), pa_parquet], batch_size=5))

    assert [len(chunk) for chunk in chunks] == [5]


def test_no_paths_yields_nothing():
    """Exhausting the generator used to raise UnboundLocalError when the loop body
    never ran."""
    assert list(stream_parquet_chunks([])) == []


def test_a_zero_row_parquet_yields_nothing(tmp_path):
    path = tmp_path / "empty.parquet"
    gpd.GeoDataFrame({"REP_AREA": []}, geometry=[], crs="EPSG:4326").to_parquet(path)

    assert list(stream_parquet_chunks([str(path)])) == []


# ---------------------------------------------------------------------------
# process_protected_area_geoms
# ---------------------------------------------------------------------------


def test_an_empty_directory_is_an_error_not_an_empty_result(tmp_path):
    """Silently returning nothing here would publish an empty PA table."""
    with pytest.raises(FileNotFoundError):
        process_protected_area_geoms(str(tmp_path), tolerance=0.1)
