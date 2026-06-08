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


def compute_pixel_area_map_km2(transform: Affine, width: int, height: int, crs=None) -> np.ndarray:
    """Compute a (height x width) array of pixel areas in km².

    Each pixel's area is its lat/lon graticule cell on the WGS84 ellipsoid, the
    same basis as the vector ``get_area_km2`` (EPSG:6933), so raster and vector
    areas are comparable. Only two raster CRSs are supported, selected via
    ``crs``; any other projected CRS raises ``NotImplementedError``:

    * geographic (e.g. EPSG:4326) — the default when ``crs`` is None; transform
      coordinates are degrees, used directly.
    * EPSG:3857 (Pseudo-Mercator, projected metres) — conformal,
      so we invert the Mercator to get each row's latitude before applying the
      same ellipsoidal area integral.

    ``transform`` units must match ``crs`` (degrees for geographic, metres for
    EPSG:3857).
    """
    # Raster-CRS coordinate of the top and bottom edge of every pixel row
    # (transform.e < 0, so each row's top edge is "above" its bottom edge).
    rows = np.arange(height)
    coord_top = transform.f + transform.e * rows
    coord_bottom = transform.f + transform.e * (rows + 1)

    is_geographic = True
    epsg = None
    if crs is not None:
        # rasterio.crs.CRS and pyproj.CRS both expose .is_geographic / .to_epsg().
        is_geographic = bool(getattr(crs, "is_geographic", True))
        try:
            epsg = crs.to_epsg()
        except Exception:
            epsg = None

    if crs is None or is_geographic:
        # Geographic CRS: transform coordinates are already degrees of lat/lon.
        lat_top = np.radians(coord_top)
        lat_bottom = np.radians(coord_bottom)
        dlon_rad = math.radians(abs(transform.a))
    elif epsg == 3857:
        # EPSG:3857: invert the spherical Mercator (radius WGS84_A_M) to recover
        # the geodetic latitude of each row edge, and convert the projected pixel
        # width (metres) to a longitude span (radians, x = R·λ).
        r = WGS84_A_M
        lat_top = np.pi / 2 - 2 * np.arctan(np.exp(-coord_top / r))
        lat_bottom = np.pi / 2 - 2 * np.arctan(np.exp(-coord_bottom / r))
        dlon_rad = abs(transform.a) / r
    else:
        raise NotImplementedError(
            "compute_pixel_area_map_km2 supports geographic CRSs and EPSG:3857 only; "
            f"got EPSG:{epsg}. Add an explicit branch for this CRS."
        )

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
