import shutil
from pathlib import Path

import geopandas as gpd
import pytest
from pmtiles.reader import MmapSource, Reader
from shapely.geometry import Point

import src.utils.tileset_pipelines.vector_pmtiles_pipeline as vpp
from src.utils.tileset_pipelines.vector_pmtiles_pipeline import (
    VectorPMTilesetConfig,
    run_vector_pmtiles_pipeline,
)


@pytest.fixture
def config():
    return VectorPMTilesetConfig(
        source_bucket="source-bucket",
        source_file="intermediates/pas.geojson",
        output_bucket="pmtiles-bucket",
        output_blob="marine_pas.pmtiles",
        archive_bucket="data-bucket",
        archive_blob="maps/marine_pas/marine_pas_Oct2026.pmtiles",
        layer_name="marine_pas",
        display_name="Marine PAs",
    )


@pytest.fixture
def mock_gdf():
    return gpd.GeoDataFrame(
        {"WDPAID": [1, 2]},
        geometry=[Point(0, 0), Point(5, 3)],
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_read(monkeypatch, mock_gdf):
    monkeypatch.setattr(
        vpp, "read_json_df", lambda bucket, blob, verbose=False: mock_gdf.copy(), raising=True
    )


@pytest.fixture
def mock_uploads(monkeypatch, tmp_path):
    """Copy each upload into tmp_path/<bucket>/<blob> so tests can inspect the result."""
    uploads = []

    def mock_upload_file_to_gcs(bucket, file_name, blob_name):
        uploads.append((bucket, blob_name))
        destination = tmp_path / bucket / blob_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_name, destination)

    monkeypatch.setattr(vpp, "upload_file_to_gcs", mock_upload_file_to_gcs, raising=True)
    return uploads


def mock_generate_vector_tiles(input_file, output_file, verbose=False):
    Path(output_file).write_bytes(b"PMTILES")


def test_uploads_latest_and_archive(config, mock_read, mock_uploads, monkeypatch):
    monkeypatch.setattr(vpp, "generate_vector_tiles", mock_generate_vector_tiles, raising=True)

    result = run_vector_pmtiles_pipeline(config)

    assert mock_uploads == [
        ("pmtiles-bucket", "marine_pas.pmtiles"),
        ("data-bucket", "maps/marine_pas/marine_pas_Oct2026.pmtiles"),
    ]
    assert result["gcs_url"] == "https://storage.googleapis.com/pmtiles-bucket/marine_pas.pmtiles"
    assert result["temp_dir"] is None


def test_process_output_is_tiled(config, mock_read, mock_uploads, monkeypatch):
    built = {}

    def mock_generate_reads_geojson(input_file, output_file, verbose=False):
        built["columns"] = set(gpd.read_file(input_file).columns)
        mock_generate_vector_tiles(input_file, output_file)

    monkeypatch.setattr(vpp, "generate_vector_tiles", mock_generate_reads_geojson, raising=True)

    def mock_process(gdf, ctx):
        gdf["source"] = ctx["source_file"]
        return gdf

    run_vector_pmtiles_pipeline(config, process=mock_process)

    assert built["columns"] == {"WDPAID", "source", "geometry"}


def test_read_source_replaces_default_reader(config, mock_gdf, mock_uploads, monkeypatch):
    monkeypatch.setattr(vpp, "generate_vector_tiles", mock_generate_vector_tiles, raising=True)
    monkeypatch.setattr(
        vpp, "read_json_df", lambda *a, **k: pytest.fail("default reader used"), raising=True
    )
    read_calls = []

    def mock_read_source(bucket, filename):
        read_calls.append((bucket, filename))
        return mock_gdf.copy()

    run_vector_pmtiles_pipeline(config, read_source=mock_read_source)

    assert read_calls == [("source-bucket", "intermediates/pas.geojson")]


def test_raises_when_pmtiles_missing(config, mock_read, mock_uploads, monkeypatch):
    monkeypatch.setattr(
        vpp, "generate_vector_tiles", lambda input_file, output_file, verbose=False: None
    )

    with pytest.raises(FileNotFoundError):
        run_vector_pmtiles_pipeline(config)

    assert mock_uploads == []


def test_keep_temp_preserves_files(config, mock_read, mock_uploads, monkeypatch):
    monkeypatch.setattr(vpp, "generate_vector_tiles", mock_generate_vector_tiles, raising=True)
    config.keep_temp = True

    result = run_vector_pmtiles_pipeline(config)
    temp_dir = Path(result["temp_dir"])

    try:
        assert (temp_dir / "marine_pas.geojson").exists()
        assert (temp_dir / "marine_pas.pmtiles").exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_tippecanoe_writes_pmtiles_with_layer_name(config, mock_read, mock_uploads, tmp_path):
    run_vector_pmtiles_pipeline(config)

    with open(tmp_path / "pmtiles-bucket" / "marine_pas.pmtiles", "rb") as f:
        metadata = Reader(MmapSource(f)).metadata()

    layer = metadata["vector_layers"][0]
    assert layer["id"] == "marine_pas"
    assert "WDPAID" in layer["fields"]
