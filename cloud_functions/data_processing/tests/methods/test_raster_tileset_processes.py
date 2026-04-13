import pytest

import src.methods.tileset_processes.raster_tileset_processes as rtp


def test_coral_reef_wrapper_calls_pipeline(monkeypatch):
    """Ensure the wrapper forwards config correctly to run_raster_tileset_pipeline."""
    calls = {}

    def mock_run(cfg):
        calls["cfg"] = cfg
        return {
            "output_blob": cfg.output_blob,
            "gcs_url": f"https://storage.googleapis.com/{cfg.bucket}/{cfg.output_blob}",
            "tile_count": 42,
            "size_mb": 1.5,
            "temp_dir": None,
        }

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    result = rtp.create_and_update_coral_reef_tileset(verbose=False)

    cfg = calls["cfg"]
    assert cfg.bucket == "dev-cogs"
    assert cfg.source_blob == "climate-resilient-corals.tif"
    assert cfg.output_blob == "maps/coral_reef_prioritization.pmtiles"
    assert cfg.color_ramp == "coral"
    assert cfg.domain == (0.0, 1.0)
    assert cfg.max_zoom == 10
    assert result["tile_count"] == 42


def test_coral_reef_wrapper_custom_params(monkeypatch):
    """Ensure custom parameters are forwarded."""
    calls = {}

    def mock_run(cfg):
        calls["cfg"] = cfg
        return {"output_blob": cfg.output_blob, "gcs_url": "", "tile_count": 0, "size_mb": 0}

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    rtp.create_and_update_coral_reef_tileset(
        bucket="custom-bucket",
        source_blob="custom/source.tif",
        output_blob="custom/output.pmtiles",
        color_ramp="viridis",
        domain=(0.0, 100.0),
        max_zoom=8,
    )

    cfg = calls["cfg"]
    assert cfg.bucket == "custom-bucket"
    assert cfg.source_blob == "custom/source.tif"
    assert cfg.output_blob == "custom/output.pmtiles"
    assert cfg.color_ramp == "viridis"
    assert cfg.domain == (0.0, 100.0)
    assert cfg.max_zoom == 8


def test_coral_reef_wrapper_propagates_errors(monkeypatch):
    """Pipeline errors should bubble up."""

    def mock_run(cfg):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(rtp, "run_raster_tileset_pipeline", mock_run, raising=True)

    with pytest.raises(RuntimeError, match="pipeline failed"):
        rtp.create_and_update_coral_reef_tileset()
