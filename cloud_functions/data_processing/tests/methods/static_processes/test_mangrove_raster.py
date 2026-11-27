import shutil
import tarfile

import numpy as np
import pytest
import rasterio
import rasterio.shutil
from rasterio.transform import from_origin

import src.methods.static_processes.mangrove_raster as mangrove_raster
from src.methods.static_processes.mangrove_raster import build_mangrove_raster

SIZE = 1024  # two 512-pixel blocks a side in the output


@pytest.fixture
def mock_stack(tmp_path):
    """A two-year stack: 2024 has mangroves in the top-left block, 2025 in the bottom-right."""
    path = tmp_path / "stack.tif"
    bands = np.zeros((2, SIZE, SIZE), dtype="uint8")
    bands[0, 10:20, 10:20] = 1
    bands[1, 600:610, 700:720] = 1
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=SIZE,
        height=SIZE,
        count=2,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(-80, 10, 0.00027, 0.00027),
        nodata=0,
    ) as dst:
        dst.write(bands)
        dst.set_band_description(1, "2024")
        dst.set_band_description(2, "2025")
    return path, bands


def test_writes_only_the_requested_year(tmp_path, mock_stack):
    stack_path, bands = mock_stack
    out_path = tmp_path / "mangroves.tif"

    build_mangrove_raster(str(stack_path), str(out_path), 2025)

    with rasterio.open(out_path) as out, rasterio.open(stack_path) as stack:
        assert out.count == 1
        assert out.nodata == 0
        assert out.crs == stack.crs
        assert out.transform == stack.transform
        np.testing.assert_array_equal(out.read(1), bands[1])


def test_leaves_blocks_without_mangroves_unwritten(tmp_path, mock_stack):
    stack_path, _ = mock_stack
    out_path = tmp_path / "mangroves.tif"

    build_mangrove_raster(str(stack_path), str(out_path), 2025)

    with rasterio.open(out_path) as out:
        written = {
            (row, col)
            for row in range(2)
            for col in range(2)
            if out.get_tag_item(f"BLOCK_OFFSET_{col}_{row}", "TIFF", bidx=1)
        }
    assert written == {(1, 1)}


@pytest.fixture
def mock_archive(tmp_path, mock_stack):
    """The stack as a .tar.gz packed on macOS: a VRT over the tile, and a "._" metadata
    file beside it that is not a VRT."""
    stack_path, _ = mock_stack
    stack_dir = tmp_path / "packed"
    stack_dir.mkdir()
    shutil.copy(stack_path, stack_dir / "tile.tif")
    rasterio.shutil.copy(stack_dir / "tile.tif", stack_dir / "stack.vrt", driver="VRT")
    (stack_dir / "._stack.vrt").write_bytes(b"\x00\x05\x16\x07 macOS metadata")

    archive = tmp_path / "stack.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stack_dir, arcname="stack")
    return archive


def test_process_ignores_macos_metadata_files(tmp_path, monkeypatch, mock_stack, mock_archive):
    _, bands = mock_stack
    uploaded = tmp_path / "uploaded.tif"

    def mock_download(bucket, blob_name, destination, verbose=True):
        shutil.copy(mock_archive, destination)

    def mock_upload(bucket, file_name, blob_name):
        shutil.copy(file_name, uploaded)

    monkeypatch.setattr(mangrove_raster, "download_file_from_gcs", mock_download)
    monkeypatch.setattr(mangrove_raster, "upload_file_to_gcs", mock_upload)

    mangrove_raster.process_mangrove_raster(year=2025, bucket="mock-bucket", verbose=False)

    with rasterio.open(uploaded) as out:
        np.testing.assert_array_equal(out.read(1), bands[1])


def test_rejects_a_year_missing_from_the_stack(tmp_path, mock_stack):
    stack_path, _ = mock_stack

    with pytest.raises(ValueError, match="no band for 1999"):
        build_mangrove_raster(str(stack_path), str(tmp_path / "mangroves.tif"), 1999)
