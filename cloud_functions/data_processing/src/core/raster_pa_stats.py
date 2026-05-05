"""Shared helpers for computing raster pixel-class areas inside protected areas.

These were originally inlined in `methods/terrestrial_habitats.py`; they are
generic enough to be reused for any country-by-country raster + PA stats job
(e.g., the climate-resilient corals marine habitat).
"""

import traceback

import geopandas as gpd
import pandas as pd
import rasterio
from joblib import Parallel, delayed
from rasterio.transform import rowcol
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import get_cover_areas
from src.utils.geo import tile_geometry
from src.utils.logger import Logger

logger = Logger()


def estimate_masked_pixel_count(src, geom):
    """Approximate count of pixels covered by a geometry's bounding box."""
    bounds = geom.bounds  # (minx, miny, maxx, maxy)

    row_min, col_min = rowcol(src.transform, bounds[0], bounds[3], op=round)
    row_max, col_max = rowcol(src.transform, bounds[2], bounds[1], op=round)

    width = abs(col_max - col_min)
    height = abs(row_max - row_min)

    return width * height


def extract_valid_polygons(geom):
    """Return a list of polygonal geometries from possibly mixed GeometryCollection."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, (Polygon, MultiPolygon)):
        return [geom]
    if isinstance(geom, GeometryCollection):
        return [
            member
            for member in geom.geoms
            if isinstance(member, (Polygon, MultiPolygon)) and not member.is_empty
        ]
    return []


def clip_geoms(tile_geoms, polygons_gdf: gpd.GeoDataFrame):
    """For each tile, return the union of `polygons_gdf` clipped to that tile."""
    clipped_geoms = []
    for tile in tile_geoms:
        subset = polygons_gdf[polygons_gdf.intersects(tile)]
        if not subset.empty:
            unioned = unary_union(subset.geometry)
            clipped = tile.intersection(unioned)
            clipped_geoms.append(clipped)
    return clipped_geoms


def compute_country_class_areas(
    country,
    country_geom,
    raster_path: str,
    class_map: dict,
    polygons_gdf: gpd.GeoDataFrame | None = None,
    tile_size_pixels: int = 8192,
    include_zero: bool = False,
):
    """Compute raster pixel-class areas (km²) within a single country.

    If `polygons_gdf` is provided, results are restricted to the intersection of
    `country_geom` with the union of those polygons (use this for protected
    area stats). If `polygons_gdf` is None or empty, the country totals over
    the full `country_geom` are returned.

    Parameters
    ----------
    country : Any
        Country identifier; written into the returned dict under "country".
    country_geom : shapely.Geometry
        Country/region boundary.
    raster_path : str
        Local path to the raster file.
    class_map : dict
        Maps raster pixel value (int) to class name (str).
    polygons_gdf : gpd.GeoDataFrame, optional
        Polygons (e.g., PAs) already filtered to this country.
    tile_size_pixels : int
        Tile edge length used to break large countries into manageable chunks.
    include_zero : bool
        Pass through to `get_cover_areas`. Set True when 0 is a real class
        (e.g., binary 0/1 rasters).

    Returns
    -------
    dict | None
        {"country": country, <class_name>: km², ..., "total": km²} or None
        if no valid pixels were found.
    """
    try:
        with rasterio.open(raster_path) as src:
            # Skip silently if the country is entirely outside raster coverage.
            # Without this, every non-overlapping country would hit
            # `rasterio.mask`'s "Input shapes do not overlap raster" ValueError
            # below and spam the warning log.
            raster_bounds = box(*src.bounds)
            if not country_geom.intersects(raster_bounds):
                return None

            tile_geoms = [
                make_valid(tile)
                for tile in tile_geometry(
                    country_geom, src.transform, tile_size_pixels=tile_size_pixels
                )
            ]

            if polygons_gdf is None:
                # No filter: cover the entire country geometry.
                clean_geoms = []
                for tile in tile_geoms:
                    clean_geoms.extend(extract_valid_polygons(tile))
            else:
                # Filter to the country ∩ polygons union. An empty `polygons_gdf`
                # naturally yields no clean_geoms and the function returns None.
                clipped = clip_geoms(tile_geoms, polygons_gdf)
                clean_geoms = []
                for geom in clipped:
                    clean_geoms.extend(extract_valid_polygons(geom))

            # Drop polygons that fall entirely outside raster coverage. Large
            # EEZs (e.g. ATF) have valid country fragments that lie far from any
            # raster pixels; without this filter `rasterio.mask` raises
            # "Input shapes do not overlap raster" for each one.
            clean_geoms = [poly for poly in clean_geoms if poly.intersects(raster_bounds)]

            results = []
            for poly in clean_geoms:
                entry = get_cover_areas(
                    src,
                    [mapping(poly)],
                    country,
                    "country",
                    class_map,
                    include_zero=include_zero,
                )
                if entry is not None:
                    results.append(entry)

            if not results:
                return None

            results_df = pd.DataFrame(results)
            class_columns = [column for column in results_df.columns if column != "country"]
            summed = results_df[class_columns].agg("sum").to_dict()
            summed["country"] = country
            return summed
    except Exception as exc:
        logger.warning(
            {
                "message": f"Error processing {country}: {exc}",
                "traceback": traceback.format_exc(),
            }
        )
        return None


def compute_class_areas_by_country(
    raster_path: str,
    regions_gdf: gpd.GeoDataFrame,
    class_map: dict,
    region_col: str = "location",
    polygons_gdf: gpd.GeoDataFrame | None = None,
    polygon_country_col: str | None = None,
    tile_size_pixels: int = 8192,
    include_zero: bool = False,
    n_jobs: int = -1,
    verbose: bool = True,
) -> pd.DataFrame:
    """For every country in `regions_gdf`, compute raster class areas.

    When `polygons_gdf` is supplied, results are restricted to the intersection
    of each country's region geometry with the polygons it contains (matched by
    `polygon_country_col`). Pass `polygons_gdf=None` to get country totals.
    e.g. Without `polygons_gdf` it produces total area of of each pixel class within
    the country. With `polygons_gdf` of protected areas it produces area of protected
    pixel class within each country.

    Returns a DataFrame with one row per processed country, columns:
    ["country", *class names that appeared, "total"].
    """
    if polygons_gdf is not None and polygon_country_col is None:
        raise ValueError("polygon_country_col must be provided when polygons_gdf is given")

    countries = regions_gdf[region_col].unique().tolist()

    def _job(country):
        country_geom = regions_gdf.loc[regions_gdf[region_col] == country, "geometry"].iloc[0]
        country_polygons = (
            polygons_gdf[polygons_gdf[polygon_country_col] == country]
            if polygons_gdf is not None
            else None
        )
        return compute_country_class_areas(
            country=country,
            country_geom=country_geom,
            raster_path=raster_path,
            class_map=class_map,
            polygons_gdf=country_polygons,
            tile_size_pixels=tile_size_pixels,
            include_zero=include_zero,
        )

    iterable = tqdm(countries) if verbose else countries
    try:
        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_job)(country) for country in iterable
        )
    except Exception as exc:
        # Joblib's loky pool can die hard (OOM-killed worker, segfault in a C
        # extension) and the exception that bubbles up is generic; log loudly so
        # the failure isn't silent at the call site.
        logger.error(
            {
                "message": "compute_class_areas_by_country parallel pool failed",
                "exception": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        raise

    stats_df = pd.DataFrame([result for result in results if result is not None])
    if not stats_df.empty:
        # Classes absent in some countries come back as NaN after concat; downstream
        # callers expect 0 for "this class had no pixels in this country".
        class_columns = [column for column in stats_df.columns if column != "country"]
        stats_df[class_columns] = stats_df[class_columns].fillna(0)
    return stats_df
