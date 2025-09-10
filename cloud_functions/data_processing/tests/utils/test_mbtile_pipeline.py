import contextlib
import json
import os
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from src.utils.mbtile_pipeline import TilesetConfig, run_tileset_pipeline


@pytest.fixture
def janitor(request):
    """
    A helper patch to ensure all temp directories are cleaned up
    Use: kept_dir = janitor(result["temp_dir"])
    """
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
            # Ignore cleanup errors to avoid masking test failures
            with contextlib.suppress(Exception):
                shutil.rmtree(path, ignore_errors=True)

    request.addfinalizer(_cleanup)
    return track


def mock_build_writes_mbtiles(temp_dir: Path, ctx: dict):
    """Stand-in for generate_mbtiles: write a tiny file as the .mbtiles artifact."""
    (temp_dir / ctx["local_mbtiles"]).write_bytes(b"MBTILES")


def mock_build_noop(temp_dir: Path, ctx: dict):
    """Build step that writes nothing (to test error on missing MBTiles)."""
    pass


def mock_upload_gcs_to_tmpdir(temp_dir: Path, ctx: dict):
    """
    Simulate 'upload to GCS' by copying the MBTiles into a local folder that represents the bucket.
    Outcome: file exists at bucket/<basename of tileset_blob_name>.
    NOTE: bucket path uses tmp_path via cfg fixture, so it is auto-cleaned by pytest.
    """
    bucket_dir = Path(ctx["bucket"])
    bucket_dir.mkdir(parents=True, exist_ok=True)
    src = temp_dir / ctx["local_mbtiles"]
    dst = bucket_dir / Path(ctx["tileset_blob_name"]).name
    dst.write_bytes(src.read_bytes())


def mock_upload_mapbox(temp_dir: Path, ctx: dict):
    """
    Simulate 'upload to Mapbox' by writing a small file in the temp dir.
    If keep_temp=True the dir is preserved; we register it with the janitor in tests.
    """
    (temp_dir / f"{ctx['tileset_id']}.uploaded.json").write_text(
        json.dumps({"tileset_id": ctx["tileset_id"], "display_name": ctx["display_name"]})
    )


def mock_process(gdf, ctx):
    """Simple pass through"""
    return gdf


# ---------- Fixtures ----------


@pytest.fixture
def cfg(tmp_path):
    """
    Base config; bucket points to a writable temp folder (pytest cleans tmp_path automatically).
    """
    return TilesetConfig(
        bucket=str(tmp_path / "fake_bucket"),
        tileset_blob_name="tiles/eez.mbtiles",
        tileset_id="org.eeztile",
        display_name="EEZ Tiles",
        local_geojson_name="eez.geojson",
        source_file="path/in/gcs/eez_source.geojson",
        local_mbtiles_name="eez.mbtiles",
        verbose=False,
        keep_temp=False,  # tests toggle this per-case
        extra=None,
    )


@pytest.fixture
def small_gdf():
    """A tiny valid GeoDataFrame that make_valid() will accept."""
    gdf = gpd.GeoDataFrame(
        {"name": ["pt1"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    return gdf


# ---------- Tests ----------


@pytest.mark.parametrize("keep_temp", [False, True])
def test_success_end_to_end_outcomes(keep_temp, cfg, small_gdf, monkeypatch, janitor):
    """
    Success path:
      - read_json_df returns a GeoDataFrame
      - process (if given) returns a GeoDataFrame (pass-through)
      - GeoJSON is written
      - MBTiles is produced
      - GCS upload produces a file in bucket dir
      - Mapbox upload creates a manifest (assertable when keep_temp=True)
      - Returned structure contains expected keys & paths
      - Temp directory behavior respects keep_temp
    Cleanup:
      - bucket under tmp_path is auto-cleaned by pytest
      - preserved temp dirs registered with janitor are always removed on teardown
    """
    cfg.keep_temp = keep_temp

    monkeypatch.setattr(
        "src.utils.mbtile_pipeline.read_json_df",
        lambda bucket, blob, verbose=False: small_gdf.copy(),
        raising=True,
    )

    result = run_tileset_pipeline(
        cfg,
        process=mock_process,
        check_credentials=lambda: None,
        build_mbtiles=mock_build_writes_mbtiles,
        upload_gcs=mock_upload_gcs_to_tmpdir,
        upload_mapbox=mock_upload_mapbox,
    )

    gcs_artifact = Path(cfg.bucket) / Path(cfg.tileset_blob_name).name
    assert gcs_artifact.exists(), "Expected uploaded MBTiles to exist in bucket directory"

    assert result["tileset_id"] == cfg.tileset_id
    assert result["gcs_blob"] == cfg.tileset_blob_name
    assert result["mbtiles_path"].endswith(cfg.local_mbtiles_name)
    assert result["geojson_path"].endswith(cfg.local_geojson_name)

    # Temp dir behavior + Mapbox manifest presence
    if keep_temp:
        kept_dir = janitor(result["temp_dir"])  # register for teardown cleanup
        assert kept_dir.exists(), "Temp directory should be preserved"
        assert (kept_dir / cfg.local_geojson_name).exists(), "GeoJSON should exist in temp dir"
        assert (kept_dir / cfg.local_mbtiles_name).exists(), "MBTiles should exist in temp dir"
        assert (kept_dir / f"{cfg.tileset_id}.uploaded.json").exists(), (
            "MBTiles mock uplaoded to GCS should exist"
        )
    else:
        assert (result["temp_dir"] is None) or (not os.path.exists(str(result["temp_dir"])))


def test_raises_when_mbtiles_missing(cfg, small_gdf, monkeypatch):
    """
    If the build step doesn't create the expected MBTiles,
    the pipeline must raise FileNotFoundError.
    All writes occur under tmp_path, so no explicit cleanup needed.
    """
    monkeypatch.setattr(
        "src.utils.mbtile_pipeline.read_json_df",
        lambda bucket, blob, verbose=False: small_gdf.copy(),
        raising=True,
    )

    with pytest.raises(FileNotFoundError):
        run_tileset_pipeline(
            cfg,
            process=mock_process,
            check_credentials=lambda: None,
            build_mbtiles=mock_build_noop,  # does NOT create mbtiles
            upload_gcs=mock_upload_gcs_to_tmpdir,
            upload_mapbox=mock_upload_mapbox,
        )


def test_credentials_error_bubbles_up(cfg, small_gdf, monkeypatch):
    """
    If the credentials checker raises, the pipeline should propagate the error.
    """
    monkeypatch.setattr(
        "src.utils.mbtile_pipeline.read_json_df",
        lambda bucket, blob, verbose=False: small_gdf.copy(),
        raising=True,
    )

    with pytest.raises(RuntimeError, match="bad creds"):
        run_tileset_pipeline(
            cfg,
            process=lambda gdf, ctx: gdf,
            check_credentials=lambda: (_ for _ in ()).throw(RuntimeError("bad creds")),
            build_mbtiles=mock_build_writes_mbtiles,
            upload_gcs=mock_upload_gcs_to_tmpdir,
            upload_mapbox=mock_upload_mapbox,
        )


def test_read_json_df_error_bubbles_up(cfg, monkeypatch):
    """
    If the input read fails, the pipeline should propagate the exception from read_json_df.
    """
    monkeypatch.setattr(
        "src.utils.mbtile_pipeline.read_json_df",
        lambda bucket, blob, verbose=False: (_ for _ in ()).throw(OSError("gcs read failed")),
        raising=True,
    )

    with pytest.raises(IOError, match="gcs read failed"):
        run_tileset_pipeline(
            cfg,
            process=lambda gdf, ctx: gdf,  # never reached
            check_credentials=lambda: None,
            build_mbtiles=mock_build_writes_mbtiles,
            upload_gcs=mock_upload_gcs_to_tmpdir,
            upload_mapbox=mock_upload_mapbox,
        )


def test_process_is_applied_and_extra_ctx_is_merged(cfg, small_gdf, monkeypatch, janitor):
    """
    Ensure cfg.extra is merged into ctx AND the process hook runs (outcome: the written
    GeoJSON contains a new value derived from ctx.extra).
    The preserved temp dir is registered for teardown cleanup via the janitor.
    """
    cfg.keep_temp = True
    cfg.extra = {"variant": "testA"}

    monkeypatch.setattr(
        "src.utils.mbtile_pipeline.read_json_df",
        lambda bucket, blob, verbose=False: small_gdf.copy(),
        raising=True,
    )

    def mock_process(gdf, ctx):
        # use ctx['variant'] to add a column whose value we can find in the geojson text
        gdf = gdf.copy()
        gdf["variant"] = ctx["variant"]
        return gdf

    result = run_tileset_pipeline(
        cfg,
        process=mock_process,
        check_credentials=lambda: None,
        build_mbtiles=mock_build_writes_mbtiles,
        upload_gcs=mock_upload_gcs_to_tmpdir,
        upload_mapbox=mock_upload_mapbox,
    )

    kept_dir = janitor(result["temp_dir"])  # register for teardown cleanup
    assert kept_dir and kept_dir.exists(), "Temp directory should be preserved when keep_temp=True"

    # The saved GeoJSON should contain our sentinel string "testA"
    geojson_text = (kept_dir / cfg.local_geojson_name).read_text(encoding="utf-8")
    assert "testA" in geojson_text, "Expected process-derived value to be present in GeoJSON"
