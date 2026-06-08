"""Tests for compute_pixel_area_map_km2, which must produce correct km² for both
geographic rasters (terrestrial habitats) and the EPSG:3857 coral raster."""

import math

import numpy as np
import pyproj
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine
from shapely.geometry import box, mapping
from shapely.ops import transform as shp_transform

from src.core.commons import get_cover_areas
from src.utils.geo import compute_pixel_area_map_km2

# Real transform from gdalinfo on the EPSG:3857 250 m coral raster.
CORAL_ORIGIN_X = -20037508.178270652890205
CORAL_ORIGIN_Y = 3977092.815081370063126
CORAL_PIXEL = 250.0
CORAL_HEIGHT = 32192
CORAL_CLASS_MAP = {0: "other-corals", 1: "climate-resilient-corals"}
_R = 6378137.0  # WGS84 semi-major axis / Pseudo-Mercator sphere radius


def _coral_transform():
    return Affine(CORAL_PIXEL, 0.0, CORAL_ORIGIN_X, 0.0, -CORAL_PIXEL, CORAL_ORIGIN_Y)


def _merc_inv_deg(y):
    return math.degrees(math.pi / 2 - 2 * math.atan(math.exp(-y / _R)))


# ---------- EPSG:3857 latitude recovery ----------


def test_pseudo_mercator_inverse_matches_gdalinfo_corners():
    """Row-edge latitudes must match gdalinfo's reported corner lat/lon."""
    assert _merc_inv_deg(CORAL_ORIGIN_Y) == pytest.approx(33.6140, abs=1e-3)
    assert _merc_inv_deg(CORAL_ORIGIN_Y - CORAL_PIXEL * CORAL_HEIGHT) == pytest.approx(
        -34.3130, abs=1e-3
    )


# ---------- EPSG:3857 pixel area vs independent equal-area polygon ----------


@pytest.mark.parametrize("row_frac", [0.0, 0.25, 0.5, 0.75, 0.999])
def test_3857_pixel_area_matches_equal_area_projection(row_frac):
    """Per-pixel km² from the raster math must match the same pixel reprojected
    to EPSG:6933 (equal-area on WGS84), the basis the vector areas use."""
    transform = _coral_transform()
    area_map = compute_pixel_area_map_km2(transform, 1, CORAL_HEIGHT, crs=CRS.from_epsg(3857))

    row = int(row_frac * (CORAL_HEIGHT - 1))
    top = CORAL_ORIGIN_Y - CORAL_PIXEL * row
    pixel = box(CORAL_ORIGIN_X, top - CORAL_PIXEL, CORAL_ORIGIN_X + CORAL_PIXEL, top)
    to_6933 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:6933", always_xy=True).transform
    expected_km2 = shp_transform(to_6933, pixel).area / 1e6

    assert area_map[row, 0] == pytest.approx(expected_km2, rel=1e-4)


def test_3857_pixel_area_varies_with_latitude():
    """Sanity: Mercator is not equal-area, so equatorial pixels cover more
    ground than high-latitude pixels (a constant area would be wrong)."""
    area_map = compute_pixel_area_map_km2(
        _coral_transform(), 1, CORAL_HEIGHT, crs=CRS.from_epsg(3857)
    )
    equator_row = int(0.494 * CORAL_HEIGHT)  # band center is ~ -0.4 deg
    edge_row = 0  # ~33.6 deg N
    assert area_map[equator_row, 0] > area_map[edge_row, 0] * 1.3


# ---------- geographic backward compatibility ----------


def test_geographic_default_unchanged_vs_explicit_4326():
    transform = Affine(0.003, 0, -180, 0, -0.003, 85)
    none_crs = compute_pixel_area_map_km2(transform, 10, 10, crs=None)
    geo_crs = compute_pixel_area_map_km2(transform, 10, 10, crs=CRS.from_epsg(4326))
    assert np.allclose(none_crs, geo_crs)


def test_geographic_pixel_area_decreases_toward_poles():
    transform = Affine(0.003, 0, -180, 0, -0.003, 85)
    area_map = compute_pixel_area_map_km2(transform, 1, 10, crs=None)
    # Rows go from 85°N downward; higher latitude (row 0) → smaller area.
    assert area_map[0, 0] < area_map[-1, 0]


# ---------- unsupported CRS ----------


def test_unsupported_projected_crs_raises():
    transform = Affine(30, 0, 500000, 0, -30, 4000000)
    with pytest.raises(NotImplementedError, match="EPSG:3857"):
        compute_pixel_area_map_km2(transform, 10, 10, crs=CRS.from_epsg(32633))  # UTM 33N


# ---------- get_cover_areas on a float32 / nan-nodata / EPSG:3857 raster ----------


def test_get_cover_areas_3857_float_nan_nodata(tmp_path):
    """Mirrors the real coral raster: Float32, values {0,1}, NoData=nan, 3857.
    nan pixels must be excluded (not leak as a spurious class), classes map
    correctly, and per-class km² equals pixel count × per-pixel area."""
    pixel = 250.0
    origin_x, origin_y = 0.0, pixel * 5
    w = h = 6
    transform = Affine(pixel, 0, origin_x, 0, -pixel, origin_y)

    arr = np.full((h, w), np.nan, dtype="float32")
    arr[1:4, 1:3] = 1.0  # climate-resilient
    arr[1:4, 3:5] = 0.0  # other corals

    raster_path = str(tmp_path / "coral.tif")
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs="EPSG:3857",
        transform=transform,
        nodata=float("nan"),
    ) as dst:
        dst.write(arr, 1)

    poly = box(origin_x, origin_y - pixel * h, origin_x + pixel * w, origin_y)
    with rasterio.open(raster_path) as src:
        res = get_cover_areas(
            src, [mapping(poly)], "TEST", "country", CORAL_CLASS_MAP, include_zero=True
        )
        area_map = compute_pixel_area_map_km2(src.transform, w, h, crs=src.crs)

    assert res is not None
    # No extra key from nan leaking through as a class.
    assert set(res) == {"country", "total", "other-corals", "climate-resilient-corals"}

    expected_per_class = area_map[1:4, 0].sum() * 2  # 2 columns over rows 1..3
    assert res["climate-resilient-corals"] == pytest.approx(expected_per_class)
    assert res["other-corals"] == pytest.approx(expected_per_class)
    assert res["total"] == pytest.approx(2 * expected_per_class)
