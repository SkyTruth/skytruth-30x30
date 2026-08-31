"""Tests for get_cover_areas, process_buffered_iho and the IHO spatial joins
(intersect_wdpa_with_iho, intersect_mpatlas_with_iho) in src/core/commons.py."""

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from shapely.geometry import Point, Polygon, box, mapping

from src.core import commons
from src.core.commons import (
    get_cover_areas,
    intersect_mpatlas_with_iho,
    intersect_wdpa_with_iho,
    process_buffered_iho,
)
from src.utils.geo import compute_pixel_area_map_km2

CLASS_MAP = {0: "class-a", 1: "class-b"}


def _write_raster(path, arr, crs, transform, nodata):
    h, w = arr.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def test_excludes_nan_nodata_and_areas_match_pixel_counts(tmp_path):
    """float32 + nan nodata on a projected (EPSG:3857) raster: nan must not leak
    in as a class, and per-class km² must equal pixel count × per-pixel area."""
    pixel = 250.0
    transform = Affine(pixel, 0, 0.0, 0, -pixel, pixel * 5)
    arr = np.full((6, 6), np.nan, dtype="float32")
    arr[1:4, 1:3] = 1.0  # 6 class-b pixels
    arr[1:4, 3:5] = 0.0  # 6 class-a pixels (same rows → equal area to class-b)

    path = str(tmp_path / "r.tif")
    _write_raster(path, arr, "EPSG:3857", transform, float("nan"))

    poly = box(0.0, pixel * 5 - pixel * 6, pixel * 6, pixel * 5)
    with rasterio.open(path) as src:
        res = get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP, include_zero=True)
        per_class = compute_pixel_area_map_km2(src.transform, 6, 6, crs=src.crs)[1:4, 0].sum() * 2

    assert set(res) == {"country", "total", "class-a", "class-b"}  # no nan-derived key
    assert res["class-a"] == pytest.approx(per_class)
    assert res["class-b"] == pytest.approx(per_class)
    assert res["total"] == pytest.approx(2 * per_class)


def test_all_zero_region_returns_none_without_include_zero(tmp_path):
    """With include_zero=False an all-zero window is treated as 'no class' → None."""
    transform = Affine(1, 0, -10, 0, -1, 10)
    arr = np.zeros((10, 10), dtype="uint8")
    path = str(tmp_path / "zeros.tif")
    _write_raster(path, arr, "EPSG:4326", transform, 255)

    poly = box(-10, -10, 10, 10)
    with rasterio.open(path) as src:
        assert get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP) is None


def test_unmapped_pixel_value_falls_back_to_generic_class_name(tmp_path):
    """A pixel value missing from class_map is reported under a class_<value> key
    rather than dropped."""
    transform = Affine(1, 0, -10, 0, -1, 10)
    arr = np.full((10, 10), 7, dtype="uint8")  # 7 is not in CLASS_MAP
    path = str(tmp_path / "seven.tif")
    _write_raster(path, arr, "EPSG:4326", transform, 255)

    poly = box(-10, -10, 10, 10)
    with rasterio.open(path) as src:
        res = get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP)
    assert "class_7" in res
    assert res["class_7"] == pytest.approx(res["total"])


def _bowtie(x, y):
    """A self-intersecting — and therefore invalid — polygon."""
    return Polygon([(x, y), (x + 2, y + 2), (x + 2, y), (x, y + 2), (x, y)])


def test_invalid_iho_geometries_are_repaired_not_dropped():
    """Every IHO row is a location, and a dropped sea area would also stop its
    neighbours being clipped against it, so invalid input must be repaired in
    place. 1906 is in UNBUFFERED_MRGID: it is passed through, but still repaired."""
    bowtie = _bowtie(0, 0)
    arctic = _bowtie(10, 10)
    assert not bowtie.is_valid and not arctic.is_valid

    iho = gpd.GeoDataFrame(
        {
            "NAME": ["Bowtie Sea", "Neighbour Sea", "Arctic Ocean"],
            "MRGID": [111, 222, 1906],
            "geometry": [bowtie, box(2, 0, 4, 2), arctic],
        },
        crs="EPSG:4326",
    )

    result = process_buffered_iho(iho, km=1, n_jobs=1)

    assert sorted(result["MRGID"]) == [111, 222, 1906]
    assert result.geometry.is_valid.all()
    # The caller's frame is left untouched by the repair.
    assert not iho.geometry.is_valid.all()


# ---------- intersect_wdpa_with_iho / intersect_mpatlas_with_iho ----------

# Two side-by-side seas sharing the x=10 edge.
SEA_A = box(0, 0, 10, 10)
SEA_B = box(10, 0, 20, 10)


def _fake_iho():
    return gpd.GeoDataFrame(
        {"MRGID": ["1", "2"], "location": ["1", "2"], "NAME": ["Sea A", "Sea B"]},
        geometry=[SEA_A, SEA_B],
        crs="EPSG:4326",
    )


def _patch_iho(monkeypatch, calls=None):
    def fake_load_iho_regions(buffer=False):
        if calls is not None:
            calls.append(buffer)
        return _fake_iho()

    monkeypatch.setattr(commons, "load_iho_regions", fake_load_iho_regions)


def _patch_wdpa(monkeypatch, gdf, calls=None):
    def fake_read_json_df(bucket_name, filename, **kwargs):
        if calls is not None:
            calls.append(filename)
        return gdf

    monkeypatch.setattr(commons, "read_json_df", fake_read_json_df)


def _wdpa_frame(geometries, pids=None, pa_def=None, **extra):
    n = len(geometries)
    return gpd.GeoDataFrame(
        {
            "WDPAID": list(range(n)),
            "WDPA_PID": pids if pids is not None else [str(i) for i in range(n)],
            "PA_DEF": pa_def if pa_def is not None else [1] * n,
            **extra,
        },
        geometry=geometries,
        crs="EPSG:4326",
    )


def test_wdpa_iho_join_pairs_each_pa_with_every_sea_it_overlaps(monkeypatch):
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame(
            [box(1, 1, 2, 2), box(5, 1, 15, 2), box(100, 50, 101, 51)],
            pids=["inside", "straddler", "elsewhere"],
        ),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    pairs = sorted(zip(result["WDPA_PID"], result["location"], strict=True))
    assert pairs == [("inside", "1"), ("straddler", "1"), ("straddler", "2")]
    assert (result["intersection_area_km2"] > 0).all()


def test_wdpa_iho_join_uses_the_marine_file_for_the_given_tolerance(monkeypatch):
    _patch_iho(monkeypatch)
    requested = []
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)]), calls=requested)

    intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert requested == ["intermediates/protected_area_geoms/marine_wdpa_0.0001.geojson"]


def test_wdpa_iho_join_uses_unbuffered_iho(monkeypatch):
    """The near-shore buffered layer is for habitats; sea assignment must use
    the true IHO boundaries."""
    buffers = []
    _patch_iho(monkeypatch, calls=buffers)
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)]))

    intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert buffers == [False]


def test_wdpa_iho_join_drops_source_columns_it_was_not_asked_for(monkeypatch):
    """Carrying the full WDPA attribute set through the overlay would multiply
    it by the sea pairs for no benefit."""
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame([box(1, 1, 2, 2)], DESIG_ENG=["Marine Park"], ISO3=["FRA"]),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert "DESIG_ENG" not in result.columns
    assert "ISO3" not in result.columns
    # Nothing collided, so no _1/_2 suffixing either.
    assert set(result.columns) == {
        "WDPAID",
        "WDPA_PID",
        "PA_DEF",
        "MRGID",
        "location",
        "geometry",
        "intersection_area_km2",
    }


def test_wdpa_iho_join_keeps_oecms_for_the_caller_to_split(monkeypatch):
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame([box(1, 1, 2, 2), box(3, 3, 4, 4)], pids=["pa", "oecm"], pa_def=[1, 0]),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert sorted(result["PA_DEF"]) == [0, 1]


def test_wdpa_iho_join_keeps_point_pas_with_no_area(monkeypatch):
    """A WDPA point stays a point when its reported area is zero. It is still in
    a sea and belongs in the PA table, so it is assigned by containment with a
    zero area rather than dropped."""
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame(
            [box(1, 1, 2, 2), Point(3, 3), Point(50, 50), None],
            pids=["polygon", "point_in_sea", "point_at_sea", "missing"],
        ),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    areas = dict(zip(result["WDPA_PID"], result["intersection_area_km2"], strict=True))
    assert areas["polygon"] > 0
    assert areas["point_in_sea"] == 0.0
    # A point outside every sea, and a row with no geometry, cannot be located.
    assert "point_at_sea" not in areas
    assert "missing" not in areas


def test_mpatlas_iho_join_keeps_point_zones_with_no_area(monkeypatch):
    """MPAtlas ships a handful of point zones; they should still reach the PA
    table, just without a measurable area."""
    _patch_iho(monkeypatch)
    mpa = gpd.GeoDataFrame(
        {
            "wdpa_id": [1, 2],
            "wdpa_pid": ["1A", "2A"],
            "zone_id": [10, 20],
            "protection_mpaguide_level": ["full", "unknown"],
        },
        geometry=[box(1, 1, 2, 2), Point(3, 3)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(commons, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)

    result = intersect_mpatlas_with_iho(bucket="b", mpa_file_name="raw/mpatlas.geojson")

    areas = dict(zip(result["zone_id"], result["intersection_area_km2"], strict=True))
    assert areas[10] > 0
    assert areas[20] == 0.0
    # The point still gets its sea, so it can be shown under that location.
    assert result.loc[result["zone_id"] == 20, "location"].tolist() == ["1"]


def test_mpatlas_iho_join_can_narrow_to_fully_highly_protected_zones(monkeypatch):
    """`compute_iho_protection_level` only wants full/high zones, and filtering
    before the overlay is much cheaper than paying for all of them."""
    _patch_iho(monkeypatch)
    mpa = gpd.GeoDataFrame(
        {
            "wdpa_id": [1, 2, 3],
            "wdpa_pid": ["1A", "2A", "3A"],
            "zone_id": [10, 20, 30],
            "protection_mpaguide_level": ["full", "high", "less"],
        },
        geometry=[box(1, 1, 2, 2), box(3, 3, 4, 4), box(5, 5, 6, 6)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(commons, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)

    result = intersect_mpatlas_with_iho(
        bucket="b", mpa_file_name="raw/mpatlas.geojson", fully_highly_only=True
    )

    assert sorted(result["zone_id"]) == [10, 20]


def test_mpatlas_iho_join_pairs_zones_with_seas_without_filtering(monkeypatch):
    """`compute_iho_protection_level` wants only full/high zones, but the join
    stays unfiltered so the PA table can use the same result."""
    _patch_iho(monkeypatch)
    mpa = gpd.GeoDataFrame(
        {
            "wdpa_id": [1, 2],
            "wdpa_pid": ["1A", "2A"],
            "zone_id": [10, 20],
            "protection_mpaguide_level": ["full", "less"],
            "name": ["Zone A", "Zone B"],
        },
        geometry=[box(1, 1, 2, 2), box(11, 1, 12, 2)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(commons, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)

    result = intersect_mpatlas_with_iho(bucket="b", mpa_file_name="raw/mpatlas.geojson")

    assert sorted(zip(result["zone_id"], result["location"], strict=True)) == [(10, "1"), (20, "2")]
    assert sorted(result["protection_mpaguide_level"]) == ["full", "less"]
    assert "name" not in result.columns
