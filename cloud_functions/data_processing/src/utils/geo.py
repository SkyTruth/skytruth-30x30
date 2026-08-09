import math

import numpy as np
import pyproj
import shapely
from rasterio.transform import Affine
from shapely import set_precision
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

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


def split_at_antimeridian(geom, reference_lon: float):
    """Repair a lon/lat geometry that wrapped across the antimeridian.

    The vertices are unwrapped onto a continuous longitude range around
    reference_lon, then split back into the ±180 range as a MultiPolygon.

    Parameters
    ----------
    geom : shapely geometry
        Polygon/MultiPolygon in EPSG:4326 that may have wrapped.
    reference_lon : float
        Longitude the geometry is actually centred on.

    Returns
    -------
    shapely geometry
        The geometry split at the antimeridian, with the same area as the
        unwrapped original.
    """

    def unwrap(coords):
        unwrapped = []
        for lon, lat, *_ in coords:
            unwrapped.append((lon - 360 * round((lon - reference_lon) / 360), lat))
        return unwrapped

    polygons = geom.geoms if hasattr(geom, "geoms") else [geom]
    unwrapped_polygons = [
        Polygon(unwrap(poly.exterior.coords), [unwrap(ring.coords) for ring in poly.interiors])
        for poly in polygons
    ]
    unwrapped = make_valid(unary_union(unwrapped_polygons))

    parts = []
    for offset in (-360, 0, 360):
        band = unwrapped.intersection(box(-180 - offset, -90, 180 - offset, 90))
        if not band.is_empty:
            parts.append(shapely.affinity.translate(band, xoff=offset))

    return make_valid(unary_union(parts)) if parts else geom


def get_area_km2(poly):
    wgs84 = pyproj.CRS("EPSG:4326")
    projected_crs = pyproj.CRS("EPSG:6933")
    transformer = pyproj.Transformer.from_crs(wgs84, projected_crs, always_xy=True)
    projected_polygon = transform(transformer.transform, poly)
    return projected_polygon.area / 1e6


def robust_unary_union(geometries):
    """``unary_union`` that falls back to validation + coordinate snapping on a
    GEOS robustness failure.

    The common path is a plain ``unary_union`` — fast, and the right answer when
    inputs are already valid (callers here validate up front). Only on a GEOS
    ``TopologyException`` ("side location conflict"), which abutting/overlapping
    EEZ seams warped into EPSG:3857 can still trigger, do we pay to ``make_valid``
    and snap coordinates to a small grid and retry. The grid is scaled to the
    coordinate magnitude so it works in any CRS — sub-millimetre in EPSG:3857,
    micro-degrees in EPSG:4326 — far finer than any habitat raster pixel, so the
    area impact is negligible.
    """
    geoms = list(geometries)
    try:
        return unary_union(geoms)
    except shapely.errors.GEOSException:
        valid = [make_valid(geom) for geom in geoms]
        scale = max((abs(coord) for geom in valid for coord in geom.bounds), default=1.0) or 1.0
        snapped = [set_precision(geom, scale * 1e-9) for geom in valid]
        return make_valid(unary_union(snapped))
