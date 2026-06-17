"""Tests for get_cover_areas in src/core/commons.py."""

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from shapely.geometry import box, mapping

from src.core.commons import get_cover_areas
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
