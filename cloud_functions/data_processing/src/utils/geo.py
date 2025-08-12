import math

import numpy as np
import pyproj
from rasterio.transform import Affine
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import transform, unary_union

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


def tile_geometry(geom, transform, tile_size_pixels=1000):
    """
    Splits the geometry’s bounding box into smaller square tiles
    and intersects them with the geometry.

    Parameters
    ----------
    geom : shapely.Geometry
        Input polygon.
    transform : Affine
        Raster affine transform.
    tile_size_pixels : int
        Number of pixels per tile edge (e.g., 1000x1000 pixels).

    Returns
    -------
    List[shapely.Geometry]
        List of clipped tile geometries.
    """
    res_x, res_y = transform.a, -transform.e
    bounds = geom.bounds
    xmin, ymin, xmax, ymax = bounds

    tiles = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            tile = box(x, y, x + res_x * tile_size_pixels, y + res_y * tile_size_pixels)
            clipped = geom.intersection(tile)
            if not clipped.is_empty:
                tiles.append(clipped)
            y += res_y * tile_size_pixels
        x += res_x * tile_size_pixels

    return tiles


def fill_polygon_holes(geom):
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    elif isinstance(geom, MultiPolygon):
        return unary_union([Polygon(p.exterior) for p in geom.geoms])
    else:
        return geom


def get_area_km2(poly):
    wgs84 = pyproj.CRS("EPSG:4326")
    projected_crs = pyproj.CRS("EPSG:6933")
    transformer = pyproj.Transformer.from_crs(wgs84, projected_crs, always_xy=True)
    projected_polygon = transform(transformer.transform, poly)
    return projected_polygon.area / 1e6
