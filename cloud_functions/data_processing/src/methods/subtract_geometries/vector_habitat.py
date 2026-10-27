import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from shapely.geometry import box
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix, polygonal_parts
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    BUCKET,
    BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    HABITAT_BY_LOCATION_FILE_PATTERN,
    TOLERANCE,
    WDPA_WITH_BUFFERED_SEAS_FILE_NAME,
)
from src.methods.subtract_geometries.io import load_pa_by_location, upload_with_archive
from src.utils.gcp import (
    read_parquet_from_gcs,  # Reads a .parquet file from GCS and returns a GeoDataFrame
)
from src.utils.geo import robust_unary_union
from src.utils.logger import Logger

logger = Logger()


def calculate_unprotected_habitat_geom(
    location_area: gpd.GeoDataFrame, location_pa: gpd.GeoDataFrame, habitat: gpd.GeoDataFrame
):
    """
    Returns the unprotected habitat within a location.

    The habitat near the location is dissolved first and clipped to the location
    boundary once, rather than clipped feature by feature. Every clip pays for the
    location's full vertex count, so on a dense archipelagic boundary that ordering,
    not the number of habitat features, is what dominates the runtime. The
    location's protected areas are then subtracted from the clipped result.

    Parameters
    ----------
    location_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a location.
    location_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a location.
    habitat : gpd.GeoDataFrame
        GeoDataFrame of habitat geometries, in the same CRS as location_area. The
        spatial index is built on first use, so pass one frame across locations
        rather than a per-location slice.

    Returns
    -------
        Single-row GeoDataFrame of unprotected habitat carrying location_area's
        columns, or an empty GeoDataFrame with those columns where the location
        holds none of the habitat.
    """
    location_area = location_area.copy()
    location_geom = location_area.geometry.union_all()

    habitat_intersections = habitat.geometry.values[
        habitat.sindex.query(location_geom, predicate="intersects")
    ]
    if len(habitat_intersections) == 0:
        return location_area.iloc[:0]

    habitat_union = polygonal_parts(
        robust_unary_union(habitat_intersections).intersection(location_geom)
    )

    if not location_pa.empty:
        habitat_union = habitat_union.difference(robust_unary_union(location_pa.geometry.values))

    if habitat_union.is_empty:
        return location_area.iloc[:0]

    location_area.geometry = [habitat_union]
    return location_area


def generate_marine_habitat_minus_pa(
    habitat: str,
    total_area_file=BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    pa_file=WDPA_WITH_BUFFERED_SEAS_FILE_NAME,
    tolerance=TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = -1,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the habitat lying inside each location's boundaries;
    saves the output to GCS as a Parquet.

    The counterpart of ``generate_total_area_minus_pa``: same inputs and the same
    per-location fan-out, but each row is a location's unprotected *habitat* rather than
    its unprotected area. Locations holding none of the habitat are dropped rather than
    written as empty rows, so the output is usually far shorter than the location list.

    Parameters
    ----------
    habitat : str
        Habitat key.
    total_area_file : str
        Filename of the buffered marine locations parquet.
    pa_file : str
        Filename of the protected areas parquet written by a buffered
        ``generate_iho_pa_intersections`` run: both estates, carrying a row per PA per
        near-shore sea area it lies in. Coastal habitats are often designated inside PAs
        that WDPA flags MARINE=0, hence both estates rather than the marine one alone.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    n_jobs : int
        Number of workers in the per-location fan-out.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet, one row per location holding habitat.
    """

    habitat_gdf = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=HABITAT_BY_LOCATION_FILE_PATTERN.format(habitat=habitat),
        verbose=verbose,
    )

    # Total areas: the land/EEZ union plus the buffered IHO sea areas
    total_area = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]

    # Get list of unique location codes
    locations = total_area["location"].unique().tolist()

    # Protected areas: the marine and terrestrial protected areas intersecting eezs and
    # buffered IHO seas
    pa = load_pa_by_location(
        read_parquet_from_gcs, pa_file, tolerance, bucket=bucket, verbose=verbose
    )

    # Build the habitat index once here rather than once per location inside the workers
    habitat_gdf.sindex.query(box(0, 0, 0, 0))

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from habitat areas..."})
    results = tqdm(
        Parallel(n_jobs=n_jobs, backend="threading", return_as="generator_unordered")(
            delayed(calculate_unprotected_habitat_geom)(
                total_area[total_area["location"] == location].reset_index(drop=True),
                pa[pa["ISO3"] == location].reset_index(drop=True),
                habitat_gdf,
            )
            for location in locations
        ),
        total=len(locations),
    )

    populated = [result for result in results if not result.empty]
    habitat_minus_pa = (
        pd.concat(populated).reset_index(drop=True) if populated else total_area.iloc[:0]
    )
    if verbose:
        logger.info({"message": f"Output file has {len(habitat_minus_pa)} rows."})

    upload_with_archive(
        habitat_minus_pa,
        CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat),
        ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat),
        bucket=bucket,
    )
