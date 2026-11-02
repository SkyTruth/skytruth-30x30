import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import BUCKET
from src.methods.subtract_geometries.io import load_pa_by_location, upload_with_archive
from src.utils.gcp import (
    read_geo_df,  # Reads a .parquet, .json or .geojson file from GCS and returns a GeoDataFrame
)
from src.utils.logger import Logger

logger = Logger()


def process_location(location_area: gpd.GeoDataFrame, location_pa: gpd.GeoDataFrame):
    """
    Subtracts protected areas from total area for a location.

    Parameters
    ----------
    location_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a location.
    location_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a location.

    Returns
    -------
        GeoDataFrame with protected areas subtracted from total area for a location.
    """
    if location_pa.empty:
        # If no protected areas, return original boundary
        return location_area
    else:
        # If protected areas found, return original boundary with protected areas removed
        pa_union = location_pa.geometry.union_all()
        location_area.geometry = location_area.geometry.difference(pa_union)
        return location_area


def generate_total_area_minus_pa(
    total_area_file: str,
    pa_file: str,
    out_file: str,
    archive_out_file: str,
    tolerance: float,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the corresponding terrestrial or marine boundaries;
    saves the output as a zipped shapefile to GCS.

    Parameters
    ----------
    bucket : str
        GCS bucket name.
    total_area_file : str
        Filename of total area geojson (GADM or EEZ).
    pa_file : str
        Filename of protected area geojson (PA or MPA).
    out_file : str
        Filename for output zipped file.
    archive_out_file : str
        Filename the archive copy is kept under.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet.
    """

    # Total areas: GADM (terrestrial) or EEZ (marine)
    total_area = read_geo_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]

    # Get list of unique location codes
    locations = total_area["location"].unique().tolist()

    # Protected areas: PA (terrestrial) or MPA (marine)
    pa = load_pa_by_location(read_geo_df, pa_file, tolerance, bucket=bucket, verbose=verbose)

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from total areas..."})
    results = tqdm(
        Parallel(n_jobs=-1, backend="loky", return_as="generator_unordered")(
            delayed(process_location)(
                total_area[total_area["location"] == location].reset_index(),
                pa[pa["ISO3"] == location].reset_index(),
            )
            for location in locations
        ),
        total=len(locations),
    )

    total_area_minus_pa = pd.concat(results).reset_index(drop=True)
    if verbose:
        logger.info({"message": f"Output file has {len(total_area_minus_pa)} rows."})

    upload_with_archive(total_area_minus_pa, out_file, archive_out_file, bucket=bucket)


def generate_location_minus_fhp_mpa(
    mpa_file: str,
    loc_file: str,
    out_file: str,
    archive_out_file: str,
    tolerance: float,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """
    Differences fully/highly protected MPAs (as defined by MPAtlas) from a location file (such as
    Global EEZs or EEZ + IHO).

    Parameters
    ----------
    bucket : str
        GCS bucket name.
    mpa_file : str
            Filename of MPAtlas area geojson.
    loc_file : str
        Filename of location data geojson.
    out_file
        Filename for output file.
    archive_out_file : str
        Filename the archive copy is kept under.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame of Location with areas intersecting Highly/Fully protected MPAs removed, saved
        to GCS as a Parquet file.
    """

    mpa = read_geo_df(
        bucket_name=bucket,
        filename=mpa_file,
        verbose=verbose,
    )

    location = read_geo_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(loc_file, tolerance),
        verbose=verbose,
    )

    # Select records where protection_mpaguide_level is full or high
    mpa_fhp = mpa[mpa["protection_mpaguide_level"].isin(["full", "high"])]

    # Keep only polygon / multipolygon records and make the geometries valid
    mpa_fhp = mpa_fhp[mpa_fhp.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    mpa_fhp.geometry = mpa_fhp.geometry.make_valid()

    location = location[location.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    location.geometry = location.geometry.make_valid()

    if verbose:
        logger.info({"message": "Subtracting fully/highly protected areas from location areas..."})

    # A zone may span multiple countries (e.g. "AUS,NZL"); one row per country
    # so its geometry is subtracted from every location it belongs to
    mpa_fhp["country"] = mpa_fhp["country"].astype(str).str.split(r"[;:,]")
    mpa_fhp = mpa_fhp.explode("country")
    mpa_fhp["country"] = mpa_fhp["country"].str.strip()

    # Difference the mpa_fhp from location; where location["location"] == mpa_fhp["country"]
    mpa_by_country = mpa_fhp.dissolve(by="country")["geometry"]

    location = location.copy()
    location["_mpa"] = location["location"].map(
        mpa_by_country
    )  # is NaN where a country has no FHP MPAS

    has_mpa = location["_mpa"].notna()

    location.loc[has_mpa, "geometry"] = location.loc[has_mpa, "geometry"].difference(
        gpd.GeoSeries(location.loc[has_mpa, "_mpa"], crs=location.crs)
    )
    non_fh_protected_location_area = location.drop(columns="_mpa")

    if verbose:
        logger.info({"message": f"Output file has {len(non_fh_protected_location_area)} rows."})

    upload_with_archive(non_fh_protected_location_area, out_file, archive_out_file, bucket=bucket)
