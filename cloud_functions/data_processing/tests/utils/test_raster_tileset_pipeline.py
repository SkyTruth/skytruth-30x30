import contextlib
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from src.utils.raster_tileset_pipeline import (
    PMTilesetConfig,
    PMTilesWriter,
    _lng_lat_to_tile,
    _render_tile,
    _tile_bounds,
    run_raster_tileset_pipeline,
)

# ---------- Fixtures ----------


@pytest.fixture
def janitor(request):
    tracked = []

    def track(path_like):
        if path_like:
            path = Path(path_like)
            tracked.append(path)
            return path
        return None

    def _cleanup():
        import shutil

        for path in tracked:
            with contextlib.suppress(Exception):
                shutil.rmtree(path, ignore_errors=True)

    request.addfinalizer(_cleanup)
    return track


def _write_rgba_raster(path: str, width: int, height: int, bounds=(-10, -10, 10, 10)):
    """Write a small RGBA GeoTIFF with opaque red pixels."""
    transform = from_bounds(*bounds, width, height)
    data = np.zeros((4, height, width), dtype=np.uint8)
    data[0, :, :] = 236  # R
    data[1, :, :] = 118  # G
    data[2, :, :] = 103  # B
    data[3, :, :] = 255  # A

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="uint8",
        count=4,
        height=height,
        width=width,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data)


def _write_source_raster(path: str, width=8, height=8, bounds=(-10, -10, 10, 10)):
    """Write a small single-band Float32 raster for pipeline tests."""
    transform = from_bounds(*bounds, width, height)
    data = np.full((height, width), 1.0, dtype=np.float32)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="float32",
        count=1,
        height=height,
        width=width,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


# ---------- _lng_lat_to_tile ----------


def test_lng_lat_to_tile_origin():
    x, y = _lng_lat_to_tile(0.0, 0.0, 1)
    assert x == 1
    assert y == 1


def test_lng_lat_to_tile_northwest_corner():
    x, y = _lng_lat_to_tile(-180.0, 85.0, 0)
    assert x == 0
    assert y == 0


def test_lng_lat_to_tile_zoom_0():
    x, y = _lng_lat_to_tile(0.0, 0.0, 0)
    assert x == 0
    assert y == 0


def test_lng_lat_to_tile_clamps():
    x, y = _lng_lat_to_tile(180.0, -85.0, 2)
    assert 0 <= x < 4
    assert 0 <= y < 4


# ---------- _tile_bounds ----------


def test_tile_bounds_zoom_0():
    west, south, east, north = _tile_bounds(0, 0, 0)
    assert west == pytest.approx(-180.0)
    assert east == pytest.approx(180.0)
    assert north == pytest.approx(85.05, abs=0.1)
    assert south == pytest.approx(-85.05, abs=0.1)


def test_tile_bounds_zoom_1_quadrants():
    # Top-left tile
    w, s, e, n = _tile_bounds(0, 0, 1)
    assert w == pytest.approx(-180.0)
    assert e == pytest.approx(0.0)
    assert n > 0

    # Bottom-right tile
    w, s, e, n = _tile_bounds(1, 1, 1)
    assert w == pytest.approx(0.0)
    assert e == pytest.approx(180.0)
    assert n < 1  # near equator


def test_tile_bounds_west_less_than_east():
    for z in range(4):
        for x in range(2**z):
            for y in range(2**z):
                w, s, e, n = _tile_bounds(x, y, z)
                assert w < e
                assert s < n


# ---------- _render_tile ----------


def test_render_tile_inside_bounds(tmp_path):
    path = str(tmp_path / "rgba.tif")
    _write_rgba_raster(path, 16, 16, bounds=(-10, -10, 10, 10))

    with rasterio.open(path) as src:
        # Zoom 1, tile (1,1) covers roughly (0, -85, 180, 0) — overlaps our raster
        png = _render_tile(src, 1, 1, 1, 256)
        assert png is not None
        assert len(png) > 0
        # PNG magic bytes
        assert png[:4] == b"\x89PNG"


def test_render_tile_outside_bounds_returns_none(tmp_path):
    path = str(tmp_path / "rgba.tif")
    _write_rgba_raster(path, 16, 16, bounds=(50, 50, 60, 60))

    with rasterio.open(path) as src:
        # Zoom 2, tile (0, 3) is in the southern hemisphere — no overlap with (50-60, 50-60)
        png = _render_tile(src, 0, 3, 2, 256)
        assert png is None


def test_render_tile_all_transparent_returns_none(tmp_path):
    """A raster with alpha=0 everywhere should produce no tile."""
    path = str(tmp_path / "transparent.tif")
    transform = from_bounds(-10, -10, 10, 10, 8, 8)
    data = np.zeros((4, 8, 8), dtype=np.uint8)  # all zeros including alpha

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="uint8",
        count=4,
        height=8,
        width=8,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data)

    with rasterio.open(path) as src:
        png = _render_tile(src, 1, 1, 1, 256)
        assert png is None


# ---------- PMTilesWriter ----------


def test_pmtiles_writer_produces_file(tmp_path):
    from pmtiles.tile import Compression, TileType, zxy_to_tileid

    output = tmp_path / "test.pmtiles"

    with open(output, "wb") as f:
        writer = PMTilesWriter(f)
        tile_id = zxy_to_tileid(0, 0, 0)
        writer.write_tile(tile_id, b"\x89PNG fake tile data")
        writer.finalize(
            header={
                "tile_type": TileType.PNG,
                "tile_compression": Compression.NONE,
                "min_zoom": 0,
                "max_zoom": 0,
                "min_lon_e7": -1800000000,
                "min_lat_e7": -900000000,
                "max_lon_e7": 1800000000,
                "max_lat_e7": 900000000,
            }
        )

    assert output.exists()
    assert output.stat().st_size > 0

    # Verify it's a valid PMTiles archive (magic bytes)
    with open(output, "rb") as f:
        magic = f.read(2)
        assert magic == b"PM"


def test_pmtiles_writer_tiles_are_sorted(tmp_path):
    from pmtiles.tile import Compression, TileType, zxy_to_tileid

    output = tmp_path / "sorted.pmtiles"

    with open(output, "wb") as f:
        writer = PMTilesWriter(f)
        # Write in reverse order — writer should sort
        for z in [2, 1, 0]:
            writer.write_tile(zxy_to_tileid(z, 0, 0), f"tile-z{z}".encode())
        writer.finalize(
            header={
                "tile_type": TileType.PNG,
                "tile_compression": Compression.NONE,
                "min_zoom": 0,
                "max_zoom": 2,
                "min_lon_e7": -1800000000,
                "min_lat_e7": -900000000,
                "max_lon_e7": 1800000000,
                "max_lat_e7": 900000000,
            }
        )

    assert output.stat().st_size > 0


# ---------- run_raster_tileset_pipeline ----------


@pytest.fixture
def pipeline_cfg(tmp_path):
    return PMTilesetConfig(
        bucket="fake-bucket",
        source_blob="cogs/test.tif",
        output_blob="tiles/test.pmtiles",
        display_name="Test Raster",
        color_ramp="coral",
        domain=(0.0, 1.0),
        min_zoom=0,
        max_zoom=1,
        tile_size=64,
        verbose=False,
        keep_temp=False,
    )


def test_pipeline_end_to_end(pipeline_cfg, tmp_path, monkeypatch, janitor):
    """Full pipeline with mocked GCS: download → colorize → render → pmtiles → upload."""
    source_path = str(tmp_path / "source.tif")
    _write_source_raster(source_path)

    uploaded = {}

    def mock_download(bucket_name, blob_name, destination_file_name, verbose=True):
        import shutil

        shutil.copy(source_path, destination_file_name)

    def mock_upload(bucket, file_name, blob_name):
        uploaded["blob_name"] = blob_name
        uploaded["file_name"] = file_name
        uploaded["size"] = Path(file_name).stat().st_size

    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.download_file_from_gcs",
        mock_download,
        raising=True,
    )
    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.upload_file_to_gcs",
        mock_upload,
        raising=True,
    )

    pipeline_cfg.keep_temp = True
    result = run_raster_tileset_pipeline(pipeline_cfg)
    janitor(result["temp_dir"])

    assert result["tile_count"] > 0
    assert result["output_blob"] == "tiles/test.pmtiles"
    assert result["size_mb"] >= 0
    assert "gcs_url" in result

    assert uploaded["blob_name"] == "tiles/test.pmtiles"
    assert uploaded["size"] > 0


def test_pipeline_cleans_up_temp(pipeline_cfg, tmp_path, monkeypatch):
    """With keep_temp=False, temp dir should be removed."""
    source_path = str(tmp_path / "source.tif")
    _write_source_raster(source_path)

    def mock_download(bucket_name, blob_name, destination_file_name, verbose=True):
        import shutil

        shutil.copy(source_path, destination_file_name)

    def mock_upload(bucket, file_name, blob_name):
        pass

    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.download_file_from_gcs",
        mock_download,
        raising=True,
    )
    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.upload_file_to_gcs",
        mock_upload,
        raising=True,
    )

    pipeline_cfg.keep_temp = False
    result = run_raster_tileset_pipeline(pipeline_cfg)

    assert result["temp_dir"] is None


def test_pipeline_download_failure_propagates(pipeline_cfg, monkeypatch):
    """If GCS download fails, pipeline should raise."""

    def mock_download_fail(**kwargs):
        raise OSError("GCS download failed")

    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.download_file_from_gcs",
        mock_download_fail,
        raising=True,
    )

    with pytest.raises(OSError, match="GCS download failed"):
        run_raster_tileset_pipeline(pipeline_cfg)


def test_pipeline_invalid_color_ramp_raises(pipeline_cfg, tmp_path, monkeypatch):
    """Invalid color ramp should raise ValueError."""
    source_path = str(tmp_path / "source.tif")
    _write_source_raster(source_path)

    def mock_download(bucket_name, blob_name, destination_file_name, verbose=True):
        import shutil

        shutil.copy(source_path, destination_file_name)

    monkeypatch.setattr(
        "src.utils.raster_tileset_pipeline.download_file_from_gcs",
        mock_download,
        raising=True,
    )

    pipeline_cfg.color_ramp = "nonexistent"

    with pytest.raises(ValueError, match="Unknown color ramp"):
        run_raster_tileset_pipeline(pipeline_cfg)
