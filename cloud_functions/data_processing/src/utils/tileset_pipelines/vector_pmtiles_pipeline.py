"""
Pipeline for converting a GeoJSON source to vector PMTiles for static hosting on GCS.
"""

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd

from src.core.map_processors import generate_vector_tiles
from src.utils.gcp import read_json_df, upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


@dataclass
class VectorPMTilesetConfig:
    source_bucket: str
    source_file: str
    output_bucket: str
    output_blob: str
    archive_bucket: str
    archive_blob: str
    layer_name: str
    display_name: str
    verbose: bool = False
    keep_temp: bool = False


Process = Callable[[gpd.GeoDataFrame, dict[str, Any]], gpd.GeoDataFrame]


def run_vector_pmtiles_pipeline(
    config: VectorPMTilesetConfig,
    *,
    process: Process | None = None,
) -> dict[str, Any]:
    """
    Run the full pipeline: read GeoJSON → process → PMTiles → upload latest and dated archive.
    """
    if config.verbose:
        logger.info({"message": f"Starting vector PMTiles pipeline for {config.display_name}..."})

    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Tippecanoe names the tile layer after the input file, so this sets the source-layer.
        geojson_local = temp_dir / f"{config.layer_name}.geojson"
        pmtiles_local = temp_dir / f"{config.layer_name}.pmtiles"

        gdf = read_json_df(config.source_bucket, config.source_file, verbose=config.verbose)

        if process:
            ctx = {
                "bucket": config.source_bucket,
                "source_file": config.source_file,
                "verbose": config.verbose,
            }
            gdf = process(gdf, ctx)

        gdf["geometry"] = gdf["geometry"].make_valid()
        gdf.to_file(geojson_local, driver="GeoJSON")

        generate_vector_tiles(
            input_file=str(geojson_local),
            output_file=str(pmtiles_local),
            verbose=config.verbose,
        )

        if not pmtiles_local.exists():
            raise FileNotFoundError(f"Expected PMTiles not found: {pmtiles_local}")

        if config.verbose:
            logger.info({"message": f"Uploading PMTiles to GCS: {config.output_blob}"})

        upload_file_to_gcs(
            bucket=config.output_bucket,
            file_name=str(pmtiles_local),
            blob_name=config.output_blob,
        )

        if config.verbose:
            logger.info({"message": f"Archiving PMTiles to GCS: {config.archive_blob}"})

        upload_file_to_gcs(
            bucket=config.archive_bucket,
            file_name=str(pmtiles_local),
            blob_name=config.archive_blob,
        )

        return {
            "output_blob": config.output_blob,
            "archive_blob": config.archive_blob,
            "gcs_url": f"https://storage.googleapis.com/{config.output_bucket}/{config.output_blob}",
            "temp_dir": str(temp_dir) if config.keep_temp else None,
        }

    except Exception as error:
        logger.error(
            {
                "message": f"Vector PMTiles pipeline failed for {config.display_name}",
                "error": str(error),
            }
        )
        raise

    finally:
        if not config.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
