import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.map_params import (
    MAPBOX_TOKEN,
    MAPBOX_USER,
)
from src.core.map_processors import generate_mbtiles, upload_to_mapbox
from src.utils.gcp import upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


@dataclass
class TilesetConfig:
    bucket: str
    tileset_blob_name: str
    tileset_id: str
    display_name: str
    local_geojson_name: str
    source_file: str
    local_mbtiles_name: str = "tiles.mbtiles"
    verbose: bool = False
    keep_temp: bool = False
    extra: dict[str, Any] = None


Hook = Callable[[Path, dict[str, Any]], None]


def _check_mapbox_credentials():
    if not MAPBOX_USER or not MAPBOX_TOKEN:
        raise ValueError("MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set")


def _generate_mbtiles(temp_dir: Path, ctx: dict[str, Any]):
    generate_mbtiles(
        input_file=str(temp_dir / ctx["local_geojson"]),
        output_file=str(temp_dir / ctx["local_mbtiles"]),
        verbose=ctx["verbose"],
    )


def _upload_gcs(temp_dir: Path, ctx: dict[str, Any]):
    upload_file_to_gcs(
        bucket=ctx["bucket"],
        file_name=str(temp_dir / ctx["local_mbtiles"]),
        blob_name=ctx["tileset_blob_name"],
    )


def _upload_mapbox(temp_dir: Path, ctx: dict[str, Any]):
    upload_to_mapbox(
        source=str(temp_dir / ctx["local_mbtiles"]),
        tileset_id=ctx["tileset_id"],
        display_name=ctx["display_name"],
        username=MAPBOX_USER,
        token=MAPBOX_TOKEN,
        verbose=ctx["verbose"],
    )


def run_tileset_pipeline(
    cfg: TilesetConfig,
    *,
    process: Hook | None = None,
    check_credentials: Callable = _check_mapbox_credentials,
    build_mbtiles: Hook = _generate_mbtiles,
    upload_gcs: Hook = _upload_gcs,
    upload_mapbox: Hook = _upload_mapbox,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "bucket": cfg.bucket,
        "tileset_blob_name": cfg.tileset_blob_name,
        "tileset_id": cfg.tileset_id,
        "display_name": cfg.display_name,
        "local_geojson": cfg.local_geojson_name,
        "local_mbtiles": cfg.local_mbtiles_name,
        "source_file": cfg.source_file,
        "verbose": cfg.verbose,
    }
    if cfg.extra:
        ctx.update(cfg.extra)

    try:
        check_credentials()
        if cfg.verbose:
            print(f"Starting {ctx['display_name']} tileset pipeline...")

        temp_mgr = tempfile.TemporaryDirectory()
        temp_dir = Path(temp_mgr.__enter__())

        try:
            if process:
                if cfg.verbose:
                    print(f"Processing {ctx['display_name']}...")
                process(temp_dir, ctx)

            geojson_path = temp_dir / ctx["local_geojson"]
            if not geojson_path.exists():
                raise FileNotFoundError(f"Expected GeoJSON not found: {geojson_path}")

            if cfg.verbose:
                print(f"Generating {ctx['display_name']} MBTiles...")
            build_mbtiles(temp_dir, ctx)

            mbtiles_path = temp_dir / ctx["local_mbtiles"]
            if not mbtiles_path.exists():
                raise FileNotFoundError(f"Expected MBTiles not found: {mbtiles_path}")

            if cfg.verbose:
                print(
                    f"Uploading {ctx['display_name']} tileset to GCS {ctx['tileset_blob_name']}..."
                )
            upload_gcs(temp_dir, ctx)

            if cfg.verbose:
                print(f"Uploading {ctx['display_name']} tileset to Mapbox...")
            upload_mapbox(temp_dir, ctx)

            return {
                "temp_dir": str(temp_dir if cfg.keep_temp else None),
                "geojson_path": str(geojson_path),
                "mbtiles_path": str(mbtiles_path),
                "gcs_blob": cfg.tileset_blob_name,
                "tileset_id": cfg.tileset_id,
            }

        finally:
            if not cfg.keep_temp:
                temp_mgr.__exit__(None, None, None)
            else:
                if cfg.verbose:
                    print(f"Preserving temp dir at {temp_dir}")

    except Exception as ex:
        logger.error(
            {"message": f"Tileset pipeline failed for {ctx['display_name']}", "error": str(ex)}
        )
        raise
