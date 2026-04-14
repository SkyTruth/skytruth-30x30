import pytest

import src.methods.tileset_processes.raster_tileset_processes as rtp
from src.core.map_params import (
    CORAL_REEF_COLOR_RAMP,
    CORAL_REEF_DOMAIN,
    CORAL_REEF_MAX_ZOOM,
    CORAL_REEF_TILESET_FILE,
    CORAL_REEF_TILESET_NAME,
)
from src.core.params import CORAL_REEF_SOURCE_FILE, RASTER_BUCKET


def test_coral_reef_wrapper_uses_constants(monkeypatch):
    """Ensure the wrapper uses the constants from params/map_params as defaults."""
    calls = {}

    def mock_run(config):
        calls["config"] = config
        return {
            "output_blob": config.output_blob,
            "gcs_url": f"https://storage.googleapis.com/{config.bucket}/{config.output_blob}",
            "tile_count": 42,
            "size_mb": 1.5,
            "temp_dir": None,
        }

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    result = rtp.create_and_update_coral_reef_tileset(verbose=False)

    config = calls["config"]
    assert config.bucket == RASTER_BUCKET
    assert config.source_blob == CORAL_REEF_SOURCE_FILE
    assert config.output_blob == CORAL_REEF_TILESET_FILE
    assert config.display_name == CORAL_REEF_TILESET_NAME
    assert config.color_ramp == CORAL_REEF_COLOR_RAMP
    assert config.domain == CORAL_REEF_DOMAIN
    assert config.max_zoom == CORAL_REEF_MAX_ZOOM
    assert result["tile_count"] == 42


def test_coral_reef_wrapper_custom_params(monkeypatch):
    """Ensure custom parameters override the defaults."""
    calls = {}

    def mock_run(config):
        calls["config"] = config
        return {"output_blob": config.output_blob, "gcs_url": "", "tile_count": 0, "size_mb": 0}

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    rtp.create_and_update_coral_reef_tileset(
        bucket="custom-bucket",
        source_blob="custom/source.tif",
        output_blob="custom/output.pmtiles",
        color_ramp="viridis",
        domain=(0.0, 100.0),
        max_zoom=8,
    )

    config = calls["config"]
    assert config.bucket == "custom-bucket"
    assert config.source_blob == "custom/source.tif"
    assert config.output_blob == "custom/output.pmtiles"
    assert config.color_ramp == "viridis"
    assert config.domain == (0.0, 100.0)
    assert config.max_zoom == 8


def test_coral_reef_wrapper_propagates_errors(monkeypatch):
    """Pipeline errors should bubble up."""

    def mock_run(config):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    with pytest.raises(RuntimeError, match="pipeline failed"):
        rtp.create_and_update_coral_reef_tileset()
