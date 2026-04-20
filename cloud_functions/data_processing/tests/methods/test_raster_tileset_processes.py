import pytest

import src.methods.tileset_processes.raster_tileset_processes as rtp
from src.core.map_params import (
    CORAL_REEF_COLOR_RAMP,
    CORAL_REEF_DOMAIN,
    CORAL_REEF_MAX_ZOOM,
    CORAL_REEF_TILESET_ARCHIVE_FILE,
    CORAL_REEF_TILESET_FILE,
    CORAL_REEF_TILESET_NAME,
    PMTILES_BUCKET,
)
from src.core.params import BUCKET, CORAL_REEF_SOURCE_FILE
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Mock the pipeline to return a result with a temp_dir containing a fake pmtiles file."""
    calls = {"pipeline": None, "uploads": []}

    def mock_run(config):
        import tempfile
        from pathlib import Path

        temp_dir = tempfile.mkdtemp()
        # Write a fake pmtiles file so the archive upload has something to read
        (Path(temp_dir) / "output.pmtiles").write_bytes(b"PMTILES_FAKE")

        calls["pipeline"] = config
        return {
            "output_blob": config.output_blob,
            "gcs_url": f"https://storage.googleapis.com/{config.output_bucket}/{config.output_blob}",
            "tile_count": 42,
            "size_mb": 1.5,
            "temp_dir": temp_dir,
        }

    def mock_upload(bucket, file_name, blob_name):
        calls["uploads"].append({"bucket": bucket, "file_name": file_name, "blob_name": blob_name})

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)
    monkeypatch.setattr(rtp, "upload_file_to_gcs", mock_upload, raising=True)

    return calls


def test_wrapper_uses_constants(mock_pipeline):
    """Ensure the wrapper uses the constants from params/map_params as defaults."""
    result = rtp.create_and_update_climate_resilient_coral_tileset(verbose=False)

    config = mock_pipeline["pipeline"]
    assert config.source_bucket == BUCKET
    assert config.source_blob == CORAL_REEF_SOURCE_FILE
    assert config.output_bucket == PMTILES_BUCKET
    assert config.output_blob == CORAL_REEF_TILESET_FILE
    assert config.display_name == CORAL_REEF_TILESET_NAME
    assert config.color_ramp == CORAL_REEF_COLOR_RAMP
    assert config.domain == CORAL_REEF_DOMAIN
    assert config.max_zoom == CORAL_REEF_MAX_ZOOM
    assert result["tile_count"] == 42


def test_wrapper_archives_to_data_bucket(mock_pipeline):
    """After pipeline completes, the PMTiles should be archived to BUCKET."""
    rtp.create_and_update_climate_resilient_coral_tileset(verbose=False)

    uploads = mock_pipeline["uploads"]
    assert len(uploads) == 1

    archive_upload = uploads[0]
    assert archive_upload["bucket"] == BUCKET
    assert archive_upload["blob_name"] == CORAL_REEF_TILESET_ARCHIVE_FILE
    assert archive_upload["file_name"].endswith("output.pmtiles")


def test_wrapper_custom_params(mock_pipeline):
    """Ensure custom parameters override the defaults."""
    rtp.create_and_update_climate_resilient_coral_tileset(
        source_bucket="custom-source",
        source_blob="custom/source.tif",
        output_bucket="custom-output",
        output_blob="custom/output.pmtiles",
        archive_bucket="custom-archive",
        archive_blob="custom/archive.pmtiles",
        color_ramp="viridis",
        domain=(0.0, 100.0),
        max_zoom=8,
    )

    config = mock_pipeline["pipeline"]
    assert config.source_bucket == "custom-source"
    assert config.output_bucket == "custom-output"
    assert config.output_blob == "custom/output.pmtiles"

    archive_upload = mock_pipeline["uploads"][0]
    assert archive_upload["bucket"] == "custom-archive"
    assert archive_upload["blob_name"] == "custom/archive.pmtiles"


def test_wrapper_raises_schedule_retry_on_failure(monkeypatch):
    """When the pipeline fails, ScheduleRetry is raised with the correct retry config."""

    def mock_run(config):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    method = "update_climate_resilient_coral_tileset"
    with pytest.raises(ScheduleRetry) as exc_info:
        rtp.create_and_update_climate_resilient_coral_tileset()

    retry_cfg = METHOD_RETRY_CONFIGS[method]
    assert exc_info.value.delay_seconds == retry_cfg["delay_seconds"]
    assert exc_info.value.max_retries == retry_cfg["max_retries"]
    assert "pipeline failed" in str(exc_info.value)
