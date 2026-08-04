import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box

from src.core.raster_pa_stats import (
    clip_geoms,
    compute_class_areas_by_location,
    compute_location_class_areas,
    estimate_masked_pixel_count,
    extract_valid_polygons,
)

CORAL_CLASS_MAP = {0: "other-corals", 1: "climate-resilient-corals"}


def _write_binary_raster(path: str, data: np.ndarray, bounds=(-10.0, -10.0, 10.0, 10.0)):
    """Write a small single-band uint8 GeoTIFF with nodata=255."""
    height, width = data.shape
    transform = from_bounds(*bounds, width, height)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="uint8",
        count=1,
        height=height,
        width=width,
        crs="EPSG:4326",
        transform=transform,
        nodata=255,
    ) as dst:
        dst.write(data.astype(np.uint8), 1)


# ---------- extract_valid_polygons ----------


def test_extract_valid_polygons_polygon():
    poly = box(0, 0, 1, 1)
    assert extract_valid_polygons(poly) == [poly]


def test_extract_valid_polygons_multipolygon():
    mp = MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])
    result = extract_valid_polygons(mp)
    assert result == [mp]


def test_extract_valid_polygons_empty():
    empty = Polygon()
    assert extract_valid_polygons(empty) == []


def test_extract_valid_polygons_geometry_collection_filters_non_polygons():
    gc = GeometryCollection([box(0, 0, 1, 1), Point(2, 2), LineString([(0, 0), (1, 1)])])
    result = extract_valid_polygons(gc)
    assert len(result) == 1
    assert isinstance(result[0], Polygon)


def test_extract_valid_polygons_none():
    assert extract_valid_polygons(None) == []


# ---------- clip_geoms ----------


def test_clip_geoms_returns_clipped_intersection():
    tile = box(0, 0, 10, 10)
    polys = gpd.GeoDataFrame(geometry=[box(5, 5, 15, 15), box(-5, -5, 2, 2)])
    result = clip_geoms([tile], polys)

    assert len(result) == 1
    # Clipped union: (5,5)-(10,10) ∪ (0,0)-(2,2). Total area = 25 + 4 = 29.
    assert result[0].area == pytest.approx(29)


def test_clip_geoms_skips_tiles_with_no_overlap():
    tile = box(100, 100, 110, 110)
    polys = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)])
    result = clip_geoms([tile], polys)
    assert result == []


def test_clip_geoms_handles_invalid_self_intersecting_geometry():
    """Invalid (e.g. reprojection-warped) polygons are validated before union,
    so clip_geoms doesn't raise a GEOS TopologyException."""
    tile = box(0, 0, 10, 10)
    bowtie = Polygon([(0, 0), (4, 4), (4, 0), (0, 4)])  # self-intersecting
    assert not bowtie.is_valid
    polys = gpd.GeoDataFrame(geometry=[bowtie, box(2, 2, 6, 6)])

    result = clip_geoms([tile], polys)

    assert len(result) == 1
    assert result[0].is_valid
    assert result[0].area > 0


# ---------- estimate_masked_pixel_count ----------


def test_estimate_masked_pixel_count(tmp_path):
    raster_path = str(tmp_path / "r.tif")
    data = np.zeros((10, 10), dtype=np.uint8)
    _write_binary_raster(raster_path, data)

    with rasterio.open(raster_path) as src:
        # Half the raster width × full raster height = 5 cols × 10 rows = 50 pixels.
        count = estimate_masked_pixel_count(src, box(-10, -10, 0, 10))
        assert count == 50


# ---------- compute_location_class_areas ----------


@pytest.fixture
def binary_coral_raster(tmp_path):
    """10x10 binary raster: top 5 rows = 1 (climate-resilient), bottom 5 = 0 (other)."""
    path = str(tmp_path / "corals.tif")
    data = np.zeros((10, 10), dtype=np.uint8)
    data[:5, :] = 1
    _write_binary_raster(path, data)
    return path


def test_compute_location_class_areas_no_pa_returns_both_classes(binary_coral_raster):
    country_geom = box(-10, -10, 10, 10)

    result = compute_location_class_areas(
        location="USA",
        location_geom=country_geom,
        raster_path=binary_coral_raster,
        class_map=CORAL_CLASS_MAP,
        polygons_gdf=None,
        include_zero=True,
    )

    assert result is not None
    assert result["location"] == "USA"
    assert "climate-resilient-corals" in result
    assert "other-corals" in result
    # The two classes split the raster equally → each ~half of total.
    assert result["climate-resilient-corals"] == pytest.approx(result["other-corals"], rel=0.05)
    assert result["climate-resilient-corals"] + result["other-corals"] == pytest.approx(
        result["total"], rel=1e-6
    )


def test_compute_location_class_areas_with_pa_filter(binary_coral_raster):
    country_geom = box(-10, -10, 10, 10)
    # PA covers only the top half (where climate-resilient pixels live).
    pa_gdf = gpd.GeoDataFrame(geometry=[box(-10, 0, 10, 10)], crs="EPSG:4326")

    result = compute_location_class_areas(
        location="USA",
        location_geom=country_geom,
        raster_path=binary_coral_raster,
        class_map=CORAL_CLASS_MAP,
        polygons_gdf=pa_gdf,
        include_zero=True,
    )

    assert result is not None
    assert "climate-resilient-corals" in result
    # Other corals are in the bottom half, outside the PA → should be absent or ~0.
    assert result.get("other-corals", 0) == pytest.approx(0, abs=1e-6)


def test_compute_location_class_areas_returns_none_without_include_zero_for_all_zeros(tmp_path):
    """All-zero location with include_zero=False short-circuits to None (legacy behavior)."""
    path = str(tmp_path / "zeros.tif")
    _write_binary_raster(path, np.zeros((10, 10), dtype=np.uint8))

    result = compute_location_class_areas(
        location="USA",
        location_geom=box(-10, -10, 10, 10),
        raster_path=path,
        class_map=CORAL_CLASS_MAP,
        polygons_gdf=None,
        include_zero=False,
    )
    assert result is None


def test_compute_location_class_areas_handles_empty_pa_gdf(binary_coral_raster):
    """A country with no PAs should return None rather than raising."""
    pa_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    result = compute_location_class_areas(
        location="USA",
        location_geom=box(-10, -10, 10, 10),
        raster_path=binary_coral_raster,
        class_map=CORAL_CLASS_MAP,
        polygons_gdf=pa_gdf,
        include_zero=True,
    )
    assert result is None


# ---------- compute_class_areas_by_country ----------


def test_compute_class_areas_by_country_two_countries(binary_coral_raster):
    regions = gpd.GeoDataFrame(
        {
            "location": ["USA", "MEX"],
            "geometry": [box(-10, 0, 10, 10), box(-10, -10, 10, 0)],
        },
        crs="EPSG:4326",
    )

    df = compute_class_areas_by_location(
        raster_path=binary_coral_raster,
        regions_gdf=regions,
        class_map=CORAL_CLASS_MAP,
        region_col="location",
        polygons_gdf=None,
        include_zero=True,
        n_jobs=1,
        verbose=False,
    )

    assert set(df["location"]) == {"USA", "MEX"}
    usa = df[df["location"] == "USA"].iloc[0]
    mex = df[df["location"] == "MEX"].iloc[0]
    # USA covers the top half (all class 1) → essentially no class 0.
    assert usa["climate-resilient-corals"] > 0
    assert usa.get("other-corals", 0) == pytest.approx(0, abs=1e-6)
    # MEX covers the bottom half (all class 0) → essentially no class 1.
    assert mex["other-corals"] > 0
    assert mex.get("climate-resilient-corals", 0) == pytest.approx(0, abs=1e-6)


def test_compute_class_areas_by_country_with_pa_filter(binary_coral_raster):
    regions = gpd.GeoDataFrame(
        {"location": ["USA"], "geometry": [box(-10, -10, 10, 10)]}, crs="EPSG:4326"
    )
    # PA covers the top half only (where class 1 lives).
    pas = gpd.GeoDataFrame(
        {"location": ["USA"], "geometry": [box(-10, 0, 10, 10)]}, crs="EPSG:4326"
    )

    df = compute_class_areas_by_location(
        raster_path=binary_coral_raster,
        regions_gdf=regions,
        class_map=CORAL_CLASS_MAP,
        region_col="location",
        polygons_gdf=pas,
        polygon_location_col="location",
        include_zero=True,
        n_jobs=1,
        verbose=False,
    )

    assert len(df) == 1
    row = df.iloc[0]
    assert row["climate-resilient-corals"] > 0
    assert row.get("other-corals", 0) == pytest.approx(0, abs=1e-6)


def test_compute_class_areas_by_country_requires_polygon_location_col(binary_coral_raster):
    regions = gpd.GeoDataFrame(
        {"location": ["USA"], "geometry": [box(-10, -10, 10, 10)]}, crs="EPSG:4326"
    )
    pas = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    with pytest.raises(ValueError, match="polygon_location_col"):
        compute_class_areas_by_location(
            raster_path=binary_coral_raster,
            regions_gdf=regions,
            class_map=CORAL_CLASS_MAP,
            polygons_gdf=pas,
            polygon_location_col=None,
            n_jobs=1,
            verbose=False,
        )
