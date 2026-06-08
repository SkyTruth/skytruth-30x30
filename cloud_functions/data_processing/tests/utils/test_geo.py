"""Tests for compute_pixel_area_map_km2 in src/utils/geo.py — per-pixel raster
areas in km² for geographic and EPSG:3857 rasters."""

import numpy as np
import pyproj
import pytest
from rasterio.crs import CRS
from rasterio.transform import Affine, from_bounds
from shapely.geometry import box
from shapely.ops import transform as shp_transform

from src.utils.geo import compute_pixel_area_map_km2

# True WGS84 ellipsoid surface area; the graticule areas should integrate to it.
WGS84_SURFACE_KM2 = 510_065_621
_TO_6933 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:6933", always_xy=True).transform


def _pixel_area_6933_km2(minx, miny, maxx, maxy):
    """Independent equal-area (EPSG:6933) area of a 3857 pixel box, in km²."""
    return shp_transform(_TO_6933, box(minx, miny, maxx, maxy)).area / 1e6


# ---------- geographic CRS ----------


def test_geographic_full_globe_sums_to_earth_surface_area():
    transform = from_bounds(-180, -90, 180, 90, 360, 180)
    area_map = compute_pixel_area_map_km2(transform, 360, 180, crs=CRS.from_epsg(4326))
    assert area_map.sum() == pytest.approx(WGS84_SURFACE_KM2, rel=1e-3)


def test_geographic_none_crs_matches_explicit_4326():
    transform = Affine(0.1, 0, -180, 0, -0.1, 90)
    assert np.allclose(
        compute_pixel_area_map_km2(transform, 50, 50, crs=None),
        compute_pixel_area_map_km2(transform, 50, 50, crs=CRS.from_epsg(4326)),
    )


def test_geographic_area_shrinks_toward_poles():
    transform = Affine(1, 0, -180, 0, -1, 90)  # rows run from 90°N downward
    col = compute_pixel_area_map_km2(transform, 1, 180, crs=None)[:, 0]
    assert col[0] < col[90]  # near-pole pixel smaller than equatorial pixel
    assert col[-1] < col[90]


def test_output_shape_matches_width_height():
    transform = Affine(1, 0, 0, 0, -1, 10)
    assert compute_pixel_area_map_km2(transform, 7, 3, crs=None).shape == (3, 7)


# ---------- EPSG:3857 ----------


@pytest.mark.parametrize("origin_y", [0.0, 5_000_000.0, -8_000_000.0])
def test_3857_pixel_area_matches_equal_area_reprojection(origin_y):
    """3857 is conformal, so per-pixel area must come from the latitude-varying
    math; cross-check against the same pixel reprojected to equal-area 6933."""
    pixel, origin_x = 10_000.0, -1_000_000.0
    transform = Affine(pixel, 0, origin_x, 0, -pixel, origin_y)
    area_map = compute_pixel_area_map_km2(transform, 1, 1, crs=CRS.from_epsg(3857))
    expected = _pixel_area_6933_km2(origin_x, origin_y - pixel, origin_x + pixel, origin_y)
    assert area_map[0, 0] == pytest.approx(expected, rel=1e-4)


def test_3857_area_varies_with_latitude():
    pixel = 100_000.0
    equator = compute_pixel_area_map_km2(
        Affine(pixel, 0, 0, 0, -pixel, pixel), 1, 1, crs=CRS.from_epsg(3857)
    )
    high_lat = compute_pixel_area_map_km2(
        Affine(pixel, 0, 0, 0, -pixel, 8_000_000 + pixel), 1, 1, crs=CRS.from_epsg(3857)
    )
    assert equator[0, 0] > high_lat[0, 0]


# ---------- unsupported CRS (non-happy path) ----------


def test_unsupported_projected_crs_raises():
    transform = Affine(30, 0, 500_000, 0, -30, 4_000_000)
    with pytest.raises(NotImplementedError, match="EPSG:3857"):
        compute_pixel_area_map_km2(transform, 10, 10, crs=CRS.from_epsg(32633))  # UTM 33N


def test_projected_crs_without_epsg_code_raises():
    # A projected CRS that doesn't resolve to an EPSG code must still refuse
    # rather than silently mis-measuring (epsg falls back to None).
    crs = CRS.from_proj4("+proj=laea +lat_0=0 +lon_0=0 +datum=WGS84 +units=m")
    transform = Affine(1000, 0, 0, 0, -1000, 0)
    with pytest.raises(NotImplementedError):
        compute_pixel_area_map_km2(transform, 5, 5, crs=crs)


# ---------- anchored to the real EPSG:3857 coral raster ----------


def test_coral_raster_transform_matches_equal_area():
    """Anchor on the actual gdalinfo transform of the 250 m EPSG:3857 coral
    raster (our concrete use case for the 3857 branch)."""
    origin_x, origin_y, pixel, height = -20037508.178270, 3977092.815081, 250.0, 32192
    transform = Affine(pixel, 0, origin_x, 0, -pixel, origin_y)
    area_map = compute_pixel_area_map_km2(transform, 1, height, crs=CRS.from_epsg(3857))
    for row in (0, height // 2, height - 1):
        top = origin_y - pixel * row
        expected = _pixel_area_6933_km2(origin_x, top - pixel, origin_x + pixel, top)
        assert area_map[row, 0] == pytest.approx(expected, rel=1e-4)
