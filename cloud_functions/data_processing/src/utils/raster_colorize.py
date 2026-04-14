"""
Utilities for colorizing single-band Float32 GeoTIFFs to RGBA for tileset generation

Reads a COG from GCS, applies a color ramp to map continuous values to RGBA,
and writes a compressed RGBA GeoTIFF suitable for tileset generation.
"""

from dataclasses import dataclass

import numpy as np
import rasterio

from src.utils.logger import Logger

logger = Logger()


@dataclass
class ColorStop:
    position: float
    color: tuple[int, int, int, int]  # RGBA


# Predefined color ramps
COLOR_RAMPS: dict[str, list[ColorStop]] = {
    "coral": [
        ColorStop(0.0, (243, 187, 179, 255)),  # lighter #EC7667
        ColorStop(1.0, (236, 118, 103, 255)),  # #EC7667
    ]
}


def _build_color_map(color_ramp: list[ColorStop], map_size: int = 256) -> np.ndarray:
    """Build a 256x4 RGBA lookup table from color stops."""
    color_map = np.zeros((map_size, 4), dtype=np.uint8)

    for i in range(map_size):
        normalized = i / (map_size - 1)

        # Find the two stops to interpolate between
        for j in range(len(color_ramp) - 1):
            lo = color_ramp[j]
            hi = color_ramp[j + 1]
            if lo.position <= normalized <= hi.position:
                fraction = (normalized - lo.position) / (hi.position - lo.position)
                for channel in range(4):
                    color_map[i, channel] = int(
                        lo.color[channel] + fraction * (hi.color[channel] - lo.color[channel])
                    )
                break
        else:
            # Beyond last stop
            for channel in range(4):
                color_map[i, channel] = color_ramp[-1].color[channel]

    return color_map


def colorize_raster(
    input_path: str,
    output_path: str,
    color_ramp_name: str = "coral",
    domain: tuple[float, float] = (0.0, 1.0),
    verbose: bool = False,
) -> None:
    """
    Colorize a single-band Float32 GeoTIFF to an RGBA GeoTIFF.

    Reads the input in blocks for memory efficiency, applies a color ramp
    to map values in `domain` to RGBA, and writes a compressed output
    with overviews suitable for tileset generation.

    Parameters
    ----------
    input_path : str
        Path to the input single-band Float32 GeoTIFF.
    output_path : str
        Path to write the output RGBA GeoTIFF.
    color_ramp_name : str
        Name of the color ramp to use. Must be a key in COLOR_RAMPS.
    domain : tuple[float, float]
        (min, max) value range for colorization. Values outside this range are clamped.
    verbose : bool
        Print progress information.
    """
    if color_ramp_name not in COLOR_RAMPS:
        raise ValueError(
            f"Unknown color ramp '{color_ramp_name}'. Available: {list(COLOR_RAMPS.keys())}"
        )

    color_ramp = COLOR_RAMPS[color_ramp_name]
    color_map = _build_color_map(color_ramp)
    domain_min, domain_max = domain

    with rasterio.open(input_path) as source:
        profile = source.profile.copy()
        profile.update(
            dtype="uint8",
            count=4,  # RGBA
            compress="deflate",
            predictor=2,
            tiled=True,
            blockxsize=512,
            blockysize=512,
            nodata=None,
        )

        if verbose:
            logger.info(
                {
                    "message": f"Colorizing {input_path} → {output_path}",
                    "size": f"{source.width}x{source.height}",
                    "color_ramp": color_ramp_name,
                    "domain": list(domain),
                }
            )

        with rasterio.open(output_path, "w", **profile) as dest:
            for _, window in source.block_windows(1):
                block = source.read(1, window=window)

                # Normalize to 0-255 color_map index
                nodata_mask = np.isnan(block)
                normalized = np.clip((block - domain_min) / (domain_max - domain_min), 0, 1)

                # NaN pixels produce invalid values during cast; they are
                # overwritten to transparent below so the warning is safe to ignore.
                with np.errstate(invalid="ignore"):
                    indices = (normalized * 255).astype(np.uint8)

                # Apply color_map
                rgba = color_map[indices]  # shape: (H, W, 4)

                # Set nodata pixels to fully transparent
                rgba[nodata_mask] = [0, 0, 0, 0]

                # Write RGBA bands
                for band_idx in range(4):
                    dest.write(rgba[:, :, band_idx], band_idx + 1, window=window)

            if verbose:
                logger.info({"message": "Building overviews..."})

            # Build overviews — only include levels that fit the image dimensions
            min_dim = min(dest.width, dest.height)
            overview_levels = [level for level in [2, 4, 8, 16, 32, 64] if min_dim // level >= 1]
            if overview_levels:
                dest.build_overviews(overview_levels, rasterio.enums.Resampling.nearest)
                dest.update_tags(ns="rio_overview", resampling="nearest")

    if verbose:
        logger.info({"message": f"Colorized raster written to {output_path}"})
