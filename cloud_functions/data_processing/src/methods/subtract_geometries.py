import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import BUCKET
from src.utils.gcp import (
    read_json_df,  # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    upload_gdf,  # Saves a GeoDataFrame to GCS as a GeoJSON or Parquet
)
from src.utils.logger import Logger

logger = Logger()


def process_country(country_area: gpd.GeoDataFrame, country_pa: gpd.GeoDataFrame):
    """
    Subtracts protected areas from total area for a country.

    Parameters
    ----------
    country_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a country.
    country_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a country.

    Returns
    -------
        GeoDataFrame with protected areas subtracted from total area for a country.
    """
    if country_pa.empty:
        # If no protected areas, return original boundary
        return country_area
    else:
        # If protected areas found, return original boundary with protected areas removed
        pa_union = country_pa.geometry.union_all()
        country_area.geometry = country_area.geometry.difference(pa_union)
        return country_area


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
    is_processed : bool
        Whether the protected areas GeoDataFrame is already processed and dissolved by country.
    out_file : str
        Filename for output zipped file.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet.
    """

    # Total areas: GADM (terrestrial) or EEZ (marine)
    total_area = read_json_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]

    # Get list of unique country codes
    countries = total_area["location"].unique().tolist()

    # Protected areas: PA (terrestrial) or MPA (marine)
    pa = read_json_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(pa_file, tolerance),
        verbose=verbose,
    )

    # Create one row per country
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from total areas..."})
    results = Parallel(n_jobs=-1, backend="loky")(
        delayed(process_country)(
            total_area[total_area["location"] == country].reset_index(),
            pa[pa["ISO3"] == country].reset_index(),
        )
        for country in tqdm(countries)
    )

    total_area_minus_pa = pd.concat(results).reset_index(drop=True)
    if verbose:
        logger.info({"message": f"Output file has {len(total_area_minus_pa)} rows."})

    # Save to GCS
    upload_gdf(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
    )

    # Save to archive
    upload_gdf(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=archive_out_file,
    )


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
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame of Location with areas intersecting Highly/Fully protected MPAs removed, saved 
        to GCS as a Parquet file.
    """

    mpa = read_json_df(
        bucket_name=bucket,
        filename=mpa_file,
        verbose=verbose,
    )

    location = read_json_df(
        bucket_name=bucket,
        filename=loc_file.replace(".geojson", f"_{tolerance}.geojson"),
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

    # Save to GCS
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=out_file,
        output_file_type=".parquet",
    )

    # Save to archive
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=archive_out_file,
        output_file_type=".parquet",
    )
