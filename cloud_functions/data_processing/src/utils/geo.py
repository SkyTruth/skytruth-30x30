import math

import numpy as np
import pyproj
from rasterio.transform import Affine
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import transform, unary_union

# WGS84 ellipsoid parameters. Raster pixel areas are computed on this same
# ellipsoid as the vector areas in `get_area_km2` (EPSG:6933 is an equal-area
# projection on WGS84), so the raster and vector area methods share one basis.
WGS84_A_M = 6378137.0  # semi-major axis (m)
WGS84_F = 1 / 298.257223563  # flattening
WGS84_E2 = WGS84_F * (2 - WGS84_F)  # first eccentricity squared
_WGS84_E = math.sqrt(WGS84_E2)


def _ellipsoid_area_from_equator(sin_lat: np.ndarray) -> np.ndarray:
    """Surface area (m²) of the WGS84 ellipsoid between the equator and a
    latitude, per radian of longitude.

    Closed form for the area of an ellipsoidal zone; integrated over the full
    globe it returns the true Earth surface area (~510.1M km²) and it preserves
    area identically to an equal-area projection (EPSG:6933). Used so raster
    graticule-cell areas share their basis with the vector ``get_area_km2``.

    Original source: https://pubs.usgs.gov/pp/1395/report.pdf eq (3-12)
    """
    e = _WGS84_E
    return (
        WGS84_A_M**2
        * (1 - WGS84_E2)
        * (sin_lat / (2 * (1 - WGS84_E2 * sin_lat**2)) + np.arctanh(e * sin_lat) / (2 * e))
    )


def compute_pixel_area_map_km2(transform: Affine, width: int, height: int) -> np.ndarray:
    """
    Computes a 2D array of pixel areas (in km²) for a georeferenced image in geographic CRS.

    Each pixel's area is the exact area of its graticule cell on the WGS84
    ellipsoid (the longitude span times the surface area between the cell's
    bounding parallels). This matches the area basis of the vector
    ``get_area_km2`` (EPSG:6933, equal-area on WGS84), so raster- and
    vector-derived habitat areas are directly comparable.

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

    # Latitudes of the top and bottom edge of every pixel row (transform.e < 0,
    # so each row's top edge is at a higher latitude than its bottom edge).
    rows = np.arange(height)
    lat_top = np.radians(transform.f + transform.e * rows)
    lat_bottom = np.radians(transform.f + transform.e * (rows + 1))

    # Pixel longitude span in radians (transform.a is pixel width in degrees).
    dlon_rad = math.radians(abs(transform.a))

    # Area of each row's pixels: longitude span × ellipsoid area between the
    # row's bounding parallels. Constant across a row, varies by latitude.
    row_area_km2 = (
        np.abs(
            _ellipsoid_area_from_equator(np.sin(lat_top))
            - _ellipsoid_area_from_equator(np.sin(lat_bottom))
        )
        * dlon_rad
        / 1e6
    )

    return np.outer(row_area_km2, np.ones(width))


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
