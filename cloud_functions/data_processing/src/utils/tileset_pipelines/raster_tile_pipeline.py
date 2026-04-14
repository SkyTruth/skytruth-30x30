"""
Pipeline for colorizing a COG and converting it to PMTiles for static hosting on GCS.

Flow:
1. Download source COG from GCS
2. Colorize Float32 → RGBA GeoTIFF
3. Render PNG tiles at each zoom level using rasterio
4. Write tiles into a PMTiles archive
5. Upload PMTiles file to GCS

"""

import io
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

from src.utils.gcp import download_file_from_gcs, upload_file_to_gcs
from src.utils.logger import Logger
from src.utils.raster_colorize import colorize_raster

logger = Logger()


@dataclass
class PMTilesetConfig:
    bucket: str
    source_blob: str  # GCS path to the source COG (e.g., "cogs/coral.tif")
    output_blob: str  # GCS path for the PMTiles output (e.g., "tiles/coral.pmtiles")
    display_name: str  # Human-readable name for logging
    color_ramp: str  # Color ramp name (e.g., "coral")
    domain: tuple[float, float]  # (min, max) value range
    min_zoom: int = 0
    max_zoom: int = 10  # Max zoom level for tile generation
    tile_size: int = 256
    verbose: bool = False
    keep_temp: bool = False


def _lng_lat_to_tile(lng: float, lat: float, zoom: int) -> tuple[int, int]:
    """
    Convert lng/lat to tile x/y at given zoom level
    using the slippy mapo tiling scheme. See:
    https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Implementations
    """
    num_tiles = 2**zoom
    tile_x = int((lng + 180.0) / 360.0 * num_tiles)
    lat_rad = math.radians(lat)
    tile_y = int(
        (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * num_tiles
    )
    tile_x = max(0, min(num_tiles - 1, tile_x))
    tile_y = max(0, min(num_tiles - 1, tile_y))
    return tile_x, tile_y


def _tile_bounds(tile_x: int, tile_y: int, zoom: int) -> tuple[float, float, float, float]:
    """Get the web mercator tile bounds in EPSG:4326 (west, south, east, north)."""
    num_tiles = 2**zoom
    west = tile_x / num_tiles * 360.0 - 180.0
    east = (tile_x + 1) / num_tiles * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * tile_y / num_tiles))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (tile_y + 1) / num_tiles))))
    return west, south, east, north


def _render_tile(
    source: rasterio.DatasetReader,
    tile_x: int,
    tile_y: int,
    zoom: int,
    tile_size: int,
) -> bytes | None:
    """
    Render a single map tile from the source RGBA GeoTIFF.
    Returns PNG bytes, or None if the tile has no data.
    """
    west, south, east, north = _tile_bounds(tile_x, tile_y, zoom)

    # Check if tile intersects source bounds
    source_bounds = source.bounds
    if west >= source_bounds.right or east <= source_bounds.left:
        return None
    if south >= source_bounds.top or north <= source_bounds.bottom:
        return None

    # Target transform for the tile in EPSG:4326
    tile_transform = from_bounds(west, south, east, north, tile_size, tile_size)

    # Read and reproject source data into the tile
    tile_data = np.zeros((4, tile_size, tile_size), dtype=np.uint8)

    for band_idx in range(1, 5):  # RGBA = bands 1-4
        reproject(
            source=rasterio.band(source, band_idx),
            destination=tile_data[band_idx - 1],
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=tile_transform,
            dst_crs="EPSG:4326",
            resampling=Resampling.nearest,
        )

    # Check if tile is entirely transparent (nodata)
    if tile_data[3].max() == 0:
        return None

    # Convert to PNG via PIL — rearrange from (4, H, W) to (H, W, 4)
    pixel_data = np.moveaxis(tile_data, 0, -1)
    image = Image.fromarray(pixel_data)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _generate_pmtiles(
    colorized_path: str,
    pmtiles_path: str,
    min_zoom: int,
    max_zoom: int,
    tile_size: int,
    verbose: bool,
) -> int:
    """
    Generate a PMTiles archive from a colorized RGBA GeoTIFF.
    Renders tiles at each zoom level and writes them into the archive.
    Returns the total number of tiles written.
    """
    tile_count = 0

    with rasterio.open(colorized_path) as source:
        source_bounds = source.bounds

        with open(pmtiles_path, "wb") as output_file:
            writer = PMTilesWriter(output_file)

            for zoom in range(min_zoom, max_zoom + 1):
                # Calculate tile range that covers the source bounds
                x_min, y_min = _lng_lat_to_tile(source_bounds.left, source_bounds.top, zoom)
                x_max, y_max = _lng_lat_to_tile(source_bounds.right, source_bounds.bottom, zoom)

                if verbose:
                    total_at_zoom = (x_max - x_min + 1) * (y_max - y_min + 1)
                    logger.info(
                        {
                            "message": f"Rendering zoom {zoom}: "
                            f"x=[{x_min}..{x_max}], y=[{y_min}..{y_max}], "
                            f"~{total_at_zoom} tiles"
                        }
                    )

                for tile_x in range(x_min, x_max + 1):
                    for tile_y in range(y_min, y_max + 1):
                        png_data = _render_tile(source, tile_x, tile_y, zoom, tile_size)
                        if png_data:
                            tile_id = zxy_to_tileid(zoom, tile_x, tile_y)
                            writer.write_tile(tile_id, png_data)
                            tile_count += 1

            writer.finalize(
                header={
                    "tile_type": TileType.PNG,
                    "tile_compression": Compression.NONE,
                    "min_zoom": min_zoom,
                    "max_zoom": max_zoom,
                    "min_lon_e7": int(source_bounds.left * 1e7),
                    "min_lat_e7": int(source_bounds.bottom * 1e7),
                    "max_lon_e7": int(source_bounds.right * 1e7),
                    "max_lat_e7": int(source_bounds.top * 1e7),
                }
            )

    return tile_count


class PMTilesWriter:
    """Minimal PMTiles v3 writer using the pmtiles library."""

    def __init__(self, output_file):
        self.output_file = output_file
        self.entries: list[tuple[int, bytes]] = []

    def write_tile(self, tile_id: int, data: bytes):
        self.entries.append((tile_id, data))

    def finalize(self, header: dict):
        from pmtiles.writer import Writer as _Writer

        writer = _Writer(self.output_file)
        for tile_id, data in sorted(self.entries, key=lambda entry: entry[0]):
            writer.write_tile(tile_id, data)
        writer.finalize(
            header=header,
            metadata={},
        )


def run_raster_tileset_pipeline(config: PMTilesetConfig) -> dict[str, Any]:
    """
    Run the full pipeline: download COG → colorize → render tiles → PMTiles → upload to GCS.

    The resulting PMTiles file is served from GCS via HTTP range requests.
    Configure the frontend layer in Strapi with type "cog" and config:
        { "url": "https://storage.googleapis.com/{bucket}/{output_blob}" }
    """
    if config.verbose:
        logger.info({"message": f"Starting raster tileset pipeline for {config.display_name}..."})

    temp_dir = Path(tempfile.mkdtemp())

    try:
        source_local = temp_dir / "source.tif"
        colorized_local = temp_dir / "colorized.tif"
        pmtiles_local = temp_dir / "output.pmtiles"

        if config.verbose:
            logger.info({"message": f"Downloading {config.source_blob} from GCS..."})

        download_file_from_gcs(
            bucket_name=config.bucket,
            blob_name=config.source_blob,
            destination_file_name=str(source_local),
            verbose=config.verbose,
        )

        if config.verbose:
            logger.info(
                {"message": f"Colorizing with ramp={config.color_ramp}, domain={config.domain}"}
            )

        colorize_raster(
            input_path=str(source_local),
            output_path=str(colorized_local),
            color_ramp_name=config.color_ramp,
            domain=config.domain,
            verbose=config.verbose,
        )

        if config.verbose:
            logger.info({"message": f"Rendering tiles z{config.min_zoom}-z{config.max_zoom}..."})

        tile_count = _generate_pmtiles(
            str(colorized_local),
            str(pmtiles_local),
            config.min_zoom,
            config.max_zoom,
            config.tile_size,
            config.verbose,
        )

        pmtiles_size_mb = pmtiles_local.stat().st_size / (1024 * 1024)
        if config.verbose:
            logger.info(
                {
                    "message": f"Uploading PMTiles to GCS: {config.output_blob}",
                    "size_mb": round(pmtiles_size_mb, 1),
                    "tile_count": tile_count,
                }
            )

        upload_file_to_gcs(
            bucket=config.bucket,
            file_name=str(pmtiles_local),
            blob_name=config.output_blob,
        )

        gcs_url = f"https://storage.googleapis.com/{config.bucket}/{config.output_blob}"

        if config.verbose:
            logger.info(
                {
                    "message": f"Pipeline complete for {config.display_name}",
                    "tile_count": tile_count,
                    "gcs_url": gcs_url,
                }
            )

        return {
            "output_blob": config.output_blob,
            "gcs_url": gcs_url,
            "tile_count": tile_count,
            "size_mb": round(pmtiles_size_mb, 1),
            "temp_dir": str(temp_dir) if config.keep_temp else None,
        }

    except Exception as error:
        logger.error(
            {
                "message": f"Raster tileset pipeline failed for {config.display_name}",
                "error": str(error),
            }
        )
        raise

    finally:
        if not config.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
