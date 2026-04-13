import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from src.utils.raster_colorize import (
    COLOR_RAMPS,
    ColorStop,
    _build_lut,
    colorize_raster,
)


# ---------- _build_lut ----------


def test_build_lut_shape_and_dtype():
    ramp = COLOR_RAMPS["coral"]
    lut = _build_lut(ramp)
    assert lut.shape == (256, 4)
    assert lut.dtype == np.uint8


def test_build_lut_endpoints_match_stops():
    ramp = [
        ColorStop(0.0, (10, 20, 30, 255)),
        ColorStop(1.0, (200, 210, 220, 255)),
    ]
    lut = _build_lut(ramp)
    np.testing.assert_array_equal(lut[0], [10, 20, 30, 255])
    np.testing.assert_array_equal(lut[255], [200, 210, 220, 255])


def test_build_lut_midpoint_interpolated():
    ramp = [
        ColorStop(0.0, (0, 0, 0, 255)),
        ColorStop(1.0, (254, 254, 254, 255)),
    ]
    lut = _build_lut(ramp)
    # Index 128 ≈ midpoint → values should be near 127
    mid = lut[128]
    assert 120 <= mid[0] <= 135


# ---------- Helpers ----------


def _write_test_raster(path: str, data: np.ndarray, bounds=(-10, -10, 10, 10)):
    """Write a small single-band Float32 GeoTIFF."""
    h, w = data.shape
    transform = from_bounds(*bounds, w, h)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="float32",
        count=1,
        height=h,
        width=w,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data.astype(np.float32), 1)


def _read_rgba(path: str) -> np.ndarray:
    """Read all 4 bands from an RGBA GeoTIFF, returns (4, H, W)."""
    with rasterio.open(path) as src:
        return src.read()


# ---------- colorize_raster ----------


def test_colorize_produces_4_band_uint8(tmp_path):
    src_path = str(tmp_path / "input.tif")
    dst_path = str(tmp_path / "output.tif")

    data = np.array([[0.0, 0.5], [1.0, np.nan]], dtype=np.float32)
    _write_test_raster(src_path, data)

    colorize_raster(src_path, dst_path, color_ramp_name="coral", domain=(0.0, 1.0))

    with rasterio.open(dst_path) as dst:
        assert dst.count == 4
        assert dst.dtypes[0] == "uint8"
        assert dst.width == 2
        assert dst.height == 2


def test_colorize_nan_becomes_transparent(tmp_path):
    src_path = str(tmp_path / "input.tif")
    dst_path = str(tmp_path / "output.tif")

    data = np.full((4, 4), np.nan, dtype=np.float32)
    _write_test_raster(src_path, data)

    colorize_raster(src_path, dst_path, color_ramp_name="coral", domain=(0.0, 1.0))

    rgba = _read_rgba(dst_path)
    alpha = rgba[3]
    assert alpha.max() == 0, "All NaN pixels should be fully transparent"


def test_colorize_valid_pixels_are_opaque(tmp_path):
    src_path = str(tmp_path / "input.tif")
    dst_path = str(tmp_path / "output.tif")

    data = np.full((4, 4), 0.5, dtype=np.float32)
    _write_test_raster(src_path, data)

    colorize_raster(src_path, dst_path, color_ramp_name="coral", domain=(0.0, 1.0))

    rgba = _read_rgba(dst_path)
    alpha = rgba[3]
    assert alpha.min() == 255, "All valid pixels should be fully opaque"


def test_colorize_binary_coral_ramp(tmp_path):
    """Binary raster: 0 and 1 should map to the two coral color stops."""
    src_path = str(tmp_path / "input.tif")
    dst_path = str(tmp_path / "output.tif")

    data = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    _write_test_raster(src_path, data)

    colorize_raster(src_path, dst_path, color_ramp_name="coral", domain=(0.0, 1.0))

    rgba = _read_rgba(dst_path)
    r, g, b = rgba[0], rgba[1], rgba[2]

    # Value 1.0 → #EC7667 = (236, 118, 103)
    assert r[0, 1] == 236
    assert g[0, 1] == 118
    assert b[0, 1] == 103

    # Value 0.0 → lighter = (243, 187, 179)
    assert r[0, 0] == 243
    assert g[0, 0] == 187
    assert b[0, 0] == 179


def test_colorize_domain_clamping(tmp_path):
    """Values outside domain should be clamped, not wrap or error."""
    src_path = str(tmp_path / "input.tif")
    dst_path = str(tmp_path / "output.tif")

    data = np.array([[-10.0, 100.0]], dtype=np.float32)
    _write_test_raster(src_path, data)

    colorize_raster(src_path, dst_path, color_ramp_name="coral", domain=(0.0, 1.0))

    rgba = _read_rgba(dst_path)
    alpha = rgba[3]
    assert alpha.min() == 255, "Out-of-range values should still be opaque (clamped, not nodata)"


def test_colorize_unknown_ramp_raises():
    with pytest.raises(ValueError, match="Unknown color ramp"):
        colorize_raster("fake.tif", "out.tif", color_ramp_name="nonexistent")
