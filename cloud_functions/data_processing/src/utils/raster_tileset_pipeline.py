"""
Pipeline for colorizing a COG and converting it to PMTiles for static hosting on GCS.

Flow:
1. Download source COG from GCS
2. Colorize Float32 → RGBA GeoTIFF
3. Render PNG tiles at each zoom level using rasterio
4. Write tiles into a PMTiles archive
5. Upload PMTiles file to GCS

No GDAL CLI dependencies — uses rasterio and pmtiles Python libraries only.
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
    """Convert lng/lat to tile x/y at given zoom level."""
    num = 2**zoom  # number of tiles on each axis given the zoom level
    x = int((lng + 180.0) / 360.0 * num)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * num)
    x = max(0, min(num - 1, x))
    y = max(0, min(num - 1, y))
    return x, y


def _tile_bounds(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """Get the web mercator tile bounds in EPSG:4326 (west, south, east, north)."""
    n = 2**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def _render_tile(
    src: rasterio.DatasetReader,
    x: int,
    y: int,
    z: int,
    tile_size: int,
) -> bytes | None:
    """
    Render a single map tile from the source RGBA GeoTIFF.
    Returns PNG bytes, or None if the tile has no data.
    """
    west, south, east, north = _tile_bounds(x, y, z)

    # Check if tile intersects source bounds
    src_bounds = src.bounds
    if west >= src_bounds.right or east <= src_bounds.left:
        return None
    if south >= src_bounds.top or north <= src_bounds.bottom:
        return None

    # Target transform for the tile in EPSG:4326
    dst_transform = from_bounds(west, south, east, north, tile_size, tile_size)

    # Read and reproject source data into the tile
    tile_data = np.zeros((4, tile_size, tile_size), dtype=np.uint8)

    for band_idx in range(1, 5):  # RGBA = bands 1-4
        reproject(
            source=rasterio.band(src, band_idx),
            destination=tile_data[band_idx - 1],
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            resampling=Resampling.nearest,
        )

    # Check if tile is entirely transparent (nodata)
    if tile_data[3].max() == 0:
        return None

    # Convert to PNG via PIL
    # Rearrange from (4, H, W) to (H, W, 4)
    img_data = np.moveaxis(tile_data, 0, -1)
    img = Image.fromarray(img_data)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


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

    with rasterio.open(colorized_path) as src:
        src_bounds = src.bounds

        with open(pmtiles_path, "wb") as f:
            writer = PMTilesWriter(f)

            for z in range(min_zoom, max_zoom + 1):
                # Calculate tile range that covers the source bounds
                x_min, y_min = _lng_lat_to_tile(src_bounds.left, src_bounds.top, z)
                x_max, y_max = _lng_lat_to_tile(src_bounds.right, src_bounds.bottom, z)

                if verbose:
                    total_at_zoom = (x_max - x_min + 1) * (y_max - y_min + 1)
                    logger.info(
                        {
                            "message": f"Rendering zoom {z}: "
                            f"x=[{x_min}..{x_max}], y=[{y_min}..{y_max}], "
                            f"~{total_at_zoom} tiles"
                        }
                    )

                for x in range(x_min, x_max + 1):
                    for y in range(y_min, y_max + 1):
                        png_data = _render_tile(src, x, y, z, tile_size)
                        if png_data:
                            tile_id = zxy_to_tileid(z, x, y)
                            writer.write_tile(tile_id, png_data)
                            tile_count += 1

            writer.finalize(
                header={
                    "tile_type": TileType.PNG,
                    "tile_compression": Compression.NONE,
                    "min_zoom": min_zoom,
                    "max_zoom": max_zoom,
                    "min_lon_e7": int(src_bounds.left * 1e7),
                    "min_lat_e7": int(src_bounds.bottom * 1e7),
                    "max_lon_e7": int(src_bounds.right * 1e7),
                    "max_lat_e7": int(src_bounds.top * 1e7),
                }
            )

    return tile_count


class PMTilesWriter:
    """Minimal PMTiles v3 writer using the pmtiles library."""

    def __init__(self, f):
        self.f = f
        self.entries: list[tuple[int, bytes]] = []

    def write_tile(self, tile_id: int, data: bytes):
        self.entries.append((tile_id, data))

    def finalize(self, header: dict):
        from pmtiles.writer import Writer as _Writer

        writer = _Writer(self.f)
        for tile_id, data in sorted(self.entries, key=lambda e: e[0]):
            writer.write_tile(tile_id, data)
        writer.finalize(
            header=header,
            metadata={},
        )


def run_raster_tileset_pipeline(cfg: PMTilesetConfig) -> dict[str, Any]:
    """
    Run the full pipeline: download COG → colorize → render tiles → PMTiles → upload to GCS.

    The resulting PMTiles file is served from GCS via HTTP range requests.
    Configure the frontend layer in Strapi with type "cog" and config:
        { "url": "https://storage.googleapis.com/{bucket}/{output_blob}" }
    """
    if cfg.verbose:
        logger.info({"message": f"Starting raster tileset pipeline for {cfg.display_name}..."})

    temp_dir = Path(tempfile.mkdtemp())

    try:
        source_local = temp_dir / "source.tif"
        colorized_local = temp_dir / "colorized.tif"
        pmtiles_local = temp_dir / "output.pmtiles"

        # 1. Download source COG from GCS
        if cfg.verbose:
            logger.info({"message": f"Downloading {cfg.source_blob} from GCS..."})

        download_file_from_gcs(
            bucket_name=cfg.bucket,
            blob_name=cfg.source_blob,
            destination_file_name=str(source_local),
            verbose=cfg.verbose,
        )

        # 2. Colorize Float32 → RGBA
        if cfg.verbose:
            logger.info({"message": f"Colorizing with ramp={cfg.color_ramp}, domain={cfg.domain}"})

        colorize_raster(
            input_path=str(source_local),
            output_path=str(colorized_local),
            color_ramp_name=cfg.color_ramp,
            domain=cfg.domain,
            verbose=cfg.verbose,
        )

        # 3. Render tiles and write PMTiles
        if cfg.verbose:
            logger.info({"message": f"Rendering tiles z{cfg.min_zoom}-z{cfg.max_zoom}..."})

        tile_count = _generate_pmtiles(
            str(colorized_local),
            str(pmtiles_local),
            cfg.min_zoom,
            cfg.max_zoom,
            cfg.tile_size,
            cfg.verbose,
        )

        # 4. Upload PMTiles to GCS
        pmtiles_size_mb = pmtiles_local.stat().st_size / (1024 * 1024)
        if cfg.verbose:
            logger.info(
                {
                    "message": f"Uploading PMTiles to GCS: {cfg.output_blob}",
                    "size_mb": round(pmtiles_size_mb, 1),
                    "tile_count": tile_count,
                }
            )

        upload_file_to_gcs(
            bucket=cfg.bucket,
            file_name=str(pmtiles_local),
            blob_name=cfg.output_blob,
        )

        gcs_url = f"https://storage.googleapis.com/{cfg.bucket}/{cfg.output_blob}"

        if cfg.verbose:
            logger.info(
                {
                    "message": f"Pipeline complete for {cfg.display_name}",
                    "tile_count": tile_count,
                    "gcs_url": gcs_url,
                }
            )

        return {
            "output_blob": cfg.output_blob,
            "gcs_url": gcs_url,
            "tile_count": tile_count,
            "size_mb": round(pmtiles_size_mb, 1),
            "temp_dir": str(temp_dir) if cfg.keep_temp else None,
        }

    except Exception as e:
        logger.error(
            {
                "message": f"Raster tileset pipeline failed for {cfg.display_name}",
                "error": str(e),
            }
        )
        raise

    finally:
        if not cfg.keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
