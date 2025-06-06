import math
import numpy as np
from rasterio.transform import Affine

# Constants
EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = (math.pi / 180) * EARTH_RADIUS_KM  # ~111.32 km


def compute_pixel_area_map_km2(transform: Affine, width: int, height: int) -> np.ndarray:
    """
    Computes a 2D array of pixel areas (in km²) for a georeferenced image in geographic CRS.

    Parameters
    ----------
    transform : Affine
        Affine transform of the raster (must be in degrees).
    width : int
        Width of the image (in pixels).
    height : int
        Height of the image (in pixels).

    Returns
    -------
    np.ndarray
        A (height x width) array of pixel areas in square kilometers.
    """

    # Get latitude of each row
    rows = np.arange(height)
    latitudes = transform.f + transform.e * rows  # transform.e is usually negative

    # Compute km/pixel in Y (latitude)
    pixel_height_km = abs(transform.e) * KM_PER_DEG_LAT

    # Compute km/pixel in X (longitude), varies with latitude
    km_per_deg_lon = KM_PER_DEG_LAT * np.cos(np.radians(latitudes))
    pixel_width_km = transform.a * km_per_deg_lon  # a is pixel width in degrees

    # Compute area per pixel (outer product of height x width)
    # pixel_height_km is constant, pixel_width_km varies per row
    area_per_pixel = np.outer(pixel_width_km, np.full(width, pixel_height_km))

    return area_per_pixel
