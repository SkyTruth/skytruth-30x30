import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely
from pyproj import CRS, Transformer
from rasterio.transform import Affine
from shapely import set_precision
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import transform, unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm

tqdm.pandas()

WGS84 = CRS.from_epsg(4326)

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


def intersect_features_with_regions(
    features: gpd.GeoDataFrame,
    regions: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Pair each feature with every region it overlaps, with the clipped area.

    One row per overlap, holding both frames' columns plus
    ``intersection_area_km2`` (EPSG:6933, as in ``get_area_km2``).
    """
    features = features.to_crs("EPSG:6933")
    regions = regions.to_crs("EPSG:6933")

    # Separate the polygonal features that can be clipped from the arealess ones.
    polygonal = features.geometry.geom_type.isin(("Polygon", "MultiPolygon"))
    clipped = gpd.overlay(features[polygonal], regions, how="intersection", keep_geom_type=True)
    clipped = clipped.assign(intersection_area_km2=clipped.geometry.area / 1e6)
    if polygonal.all():
        return clipped

    # Break out non-polygonal features (rare, but would break gpd.overlay) specifically
    # to keep for the PA tables
    located = features[~polygonal].sjoin(regions, predicate="intersects", lsuffix="1", rsuffix="2")
    located = located.drop(columns="index_2").assign(intersection_area_km2=np.nan)

    return pd.concat([clipped, located], ignore_index=True)


def _shift_negative_longitudes(x, y, z=None):
    """Temporarily move negative longitudes into the 0–360 range."""
    if np.isscalar(x):
        shifted_x = x + 360 if x < 0 else x
    else:
        x = np.asarray(x)
        shifted_x = np.where(x < 0, x + 360, x)

    return (shifted_x, y, z) if z is not None else (shifted_x, y)


def _wrap_to_180(geom):
    """
    Split an unwrapped geometry at antimeridians and return all polygon
    parts using conventional -180–180 longitude coordinates.
    """
    if geom is None or geom.is_empty:
        return geom

    geom = shapely.make_valid(geom)
    minx, _, maxx, _ = geom.bounds

    first_strip = math.floor((minx + 180) / 360)
    last_strip = math.floor((maxx + 180) / 360)

    pieces = []

    for strip_number in range(first_strip, last_strip + 1):
        longitude_strip = box(
            -180 + 360 * strip_number,
            -90,
            180 + 360 * strip_number,
            90,
        )

        piece = geom.intersection(longitude_strip)

        # Exclude intersections consisting only of lines or points.
        if not piece.is_empty and piece.area > 0:
            piece = translate(
                piece,
                xoff=-360 * strip_number,
            )
            pieces.append(piece)

    if not pieces:
        return geom

    return _ensure_valid(shapely.union_all(pieces))


def _ensure_valid(geom):
    """Repair ``geom``, but only when it needs repairing.

    ``make_valid`` rebuilds a geometry whether or not it is already valid, and on
    dense polygons that rebuild costs far more than the ``is_valid`` check that
    can rule it out.
    """
    return geom if geom.is_valid else shapely.make_valid(geom)


def buffer_km(geom, km=2, src_crs="EPSG:4326"):
    """
    Buffer a geometry in meters using an appropriate local projection.

    Input must be EPSG:4326. Round-tripping through another CRS would mean two
    extra passes over every coordinate, and ``shapely.ops.transform`` rebuilds
    the geometry even when the transform is the identity — costly on the dense
    ocean polygons this is used for. Reproject before calling instead.

    The returned geometry:
      - is in EPSG:4326;
      - is repaired when it is not already valid;
      - uses -180–180 longitudes;
      - is split at the antimeridian when necessary.

    Geometry touching a pole is rejected rather than buffered
    """
    if geom is None or geom.is_empty:
        return geom

    if CRS.from_user_input(src_crs) != WGS84:
        raise ValueError(f"buffer_km expects EPSG:4326 geometry, got {src_crs}")

    geographic = _ensure_valid(geom)

    minx, miny, maxx, maxy = geographic.bounds

    if maxy >= 89.999 or miny <= -89.999:
        raise NotImplementedError(
            "buffer_km cannot buffer geometry that touches a pole; exclude it upstream"
        )

    # Make an ordinary antimeridian-crossing polygon continuous
    # before selecting its projection and buffering it.
    if maxx - minx > 180:
        geographic = _ensure_valid(
            transform(
                _shift_negative_longitudes,
                geographic,
            )
        )

    center = geographic.centroid

    metric_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )

    to_metric = Transformer.from_crs(
        WGS84,
        metric_crs,
        always_xy=True,
        force_over=True,
    ).transform

    metric_to_wgs84 = Transformer.from_crs(
        metric_crs,
        WGS84,
        always_xy=True,
        force_over=True,
    ).transform

    projected = _ensure_valid(transform(to_metric, geographic))

    buffered_projected = _ensure_valid(projected.buffer(km * 1_000))

    buffered_wgs84 = _ensure_valid(transform(metric_to_wgs84, buffered_projected))

    # Restore conventional longitude coordinates. This splits crossing
    # polygons instead of shifting the complete final polygon by 360°.
    result = _wrap_to_180(buffered_wgs84)

    return result
