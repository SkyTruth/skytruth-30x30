"""
Utilities for colorizing single-band Float32 GeoTIFFs to RGBA for Mapbox upload.

Reads a COG from GCS, applies a color ramp to map continuous values to RGBA,
and writes a compressed RGBA GeoTIFF suitable for upload to Mapbox as a raster tileset.
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
    ],
    "viridis": [
        ColorStop(0.0, (68, 1, 84, 255)),
        ColorStop(0.25, (59, 82, 139, 255)),
        ColorStop(0.5, (33, 145, 140, 255)),
        ColorStop(0.75, (94, 201, 98, 255)),
        ColorStop(1.0, (253, 231, 37, 255)),
    ],
    "blues": [
        ColorStop(0.0, (247, 251, 255, 255)),
        ColorStop(0.25, (198, 219, 239, 255)),
        ColorStop(0.5, (107, 174, 214, 255)),
        ColorStop(0.75, (33, 113, 181, 255)),
        ColorStop(1.0, (8, 48, 107, 255)),
    ],
}


def _build_lut(color_ramp: list[ColorStop], lut_size: int = 256) -> np.ndarray:
    """Build a 256x4 RGBA lookup table from color stops."""
    lut = np.zeros((lut_size, 4), dtype=np.uint8)

    for i in range(lut_size):
        t = i / (lut_size - 1)

        # Find the two stops to interpolate between
        for j in range(len(color_ramp) - 1):
            lo = color_ramp[j]
            hi = color_ramp[j + 1]
            if lo.position <= t <= hi.position:
                seg_t = (t - lo.position) / (hi.position - lo.position)
                for c in range(4):
                    lut[i, c] = int(lo.color[c] + seg_t * (hi.color[c] - lo.color[c]))
                break
        else:
            # Beyond last stop
            for c in range(4):
                lut[i, c] = color_ramp[-1].color[c]

    return lut


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
    with overviews suitable for Mapbox upload.

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
    lut = _build_lut(color_ramp)
    vmin, vmax = domain

    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
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
                    "size": f"{src.width}x{src.height}",
                    "color_ramp": color_ramp_name,
                    "domain": list(domain),
                }
            )

        with rasterio.open(output_path, "w", **profile) as dst:
            for _, window in src.block_windows(1):
                data = src.read(1, window=window)

                # Normalize to 0-255 LUT index
                nodata_mask = np.isnan(data)
                normalized = np.clip((data - vmin) / (vmax - vmin), 0, 1)
                indices = (normalized * 255).astype(np.uint8)

                # Apply LUT
                rgba = lut[indices]  # shape: (H, W, 4)

                # Set nodata pixels to fully transparent
                rgba[nodata_mask] = [0, 0, 0, 0]

                # Write RGBA bands
                for band_idx in range(4):
                    dst.write(rgba[:, :, band_idx], band_idx + 1, window=window)

            if verbose:
                logger.info({"message": "Building overviews..."})

            # Build overviews — only include levels that fit the image dimensions
            min_dim = min(dst.width, dst.height)
            overview_levels = [f for f in [2, 4, 8, 16, 32, 64] if min_dim // f >= 1]
            if overview_levels:
                dst.build_overviews(overview_levels, rasterio.enums.Resampling.nearest)
                dst.update_tags(ns="rio_overview", resampling="nearest")

    if verbose:
        logger.info({"message": f"Colorized raster written to {output_path}"})
