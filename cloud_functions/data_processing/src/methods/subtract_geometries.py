import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from shapely.geometry import box
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    BUCKET,
    BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    HABITAT_BY_LOCATION_FILE_PATTERN,
    TOLERANCE,
    WDPA_MARINE_WITH_SEAS_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.core.processors import filter_protected_planet
from src.utils.gcp import (
    read_json_df,  # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    read_parquet_from_gcs,  # Reads a .parquet file from GCS and returns a GeoDataFrame
    upload_gdf,  # Saves a GeoDataFrame to GCS as a GeoJSON or Parquet
)
from src.utils.geo import robust_unary_union
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


def process_country_habitat(
    country_area: gpd.GeoDataFrame, country_pa: gpd.GeoDataFrame, habitat: gpd.GeoDataFrame
):
    """
    Returns the unprotected habitat within a country.

    The habitat near the country is dissolved first and clipped to the country
    boundary once, rather than clipped feature by feature. Every clip pays for the
    country's full vertex count, so on a dense archipelagic boundary that ordering,
    not the number of habitat features, is what dominates the runtime. The
    country's protected areas are then subtracted from the clipped result.

    Parameters
    ----------
    country_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a country.
    country_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a country.
    habitat : gpd.GeoDataFrame
        GeoDataFrame of habitat geometries, in the same CRS as country_area. The
        spatial index is built on first use, so pass one frame across countries
        rather than a per-country slice.

    Returns
    -------
        Single-row GeoDataFrame of unprotected habitat carrying country_area's
        columns, or an empty GeoDataFrame with those columns where the country
        holds none of the habitat.
    """
    country_area = country_area.copy()
    country_geom = country_area.geometry.union_all()

    nearby = habitat.geometry.values[habitat.sindex.query(country_geom, predicate="intersects")]
    if len(nearby) == 0:
        return country_area.iloc[:0]

    habitat_union = robust_unary_union(nearby).intersection(country_geom)

    if not country_pa.empty:
        habitat_union = habitat_union.difference(robust_unary_union(country_pa.geometry.values))

    if habitat_union.is_empty:
        return country_area.iloc[:0]

    country_area.geometry = [habitat_union]
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
    pa_file = add_tolerance_suffix(pa_file, tolerance)
    read_pa = read_parquet_from_gcs if pa_file.endswith(".parquet") else read_json_df
    pa = read_pa(
        bucket_name=bucket,
        filename=pa_file,
        verbose=verbose,
    ).pipe(filter_protected_planet)

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


def generate_habitat_minus_pa(
    habitat: str,
    total_area_file=BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    marine_pa_file=WDPA_MARINE_WITH_SEAS_FILE_NAME,
    terrestrial_pa_file=WDPA_TERRESTRIAL_FILE_NAME,
    tolerance=TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = 2,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the habitat lying inside each country's boundaries;
    saves the output to GCS as a Parquet.

    The counterpart of ``generate_total_area_minus_pa``: same inputs and the same
    per-country fan-out, but each row is a country's unprotected *habitat* rather than
    its unprotected area. Countries holding none of the habitat are dropped rather than
    written as empty rows, so the output is usually far shorter than the location list.

    Parameters
    ----------
    habitat : str
        Habitat key.
    total_area_file : str
        Filename of the buffered marine locations parquet.
    marine_pa_file : str
        Filename of the marine protected areas parquet.
    terrestrial_pa_file : str
        Filename of the terrestrial protected areas geojson. Coastal habitats are often
        designated inside PAs that WDPA flags MARINE=0, so both estates are subtracted;
        WDPAIDs do not repeat across the two, so they concatenate without deduplication.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet, one row per country holding habitat.
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

    # Get list of unique country codes
    countries = total_area["location"].unique().tolist()

    # Protected areas: the marine and terrestrial estates together
    marine_pa = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(marine_pa_file, tolerance),
        verbose=verbose,
    )
    terrestrial_pa = read_json_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(terrestrial_pa_file, tolerance),
        verbose=verbose,
    )
    pa = pd.concat([marine_pa, terrestrial_pa], ignore_index=True).pipe(filter_protected_planet)

    # Create one row per country
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()

    # Build the habitat index once here rather than once per country inside the workers
    habitat_gdf.sindex.query(box(0, 0, 0, 0))

    # Subtract geometries. Threading, not loky: the workers share one read-only habitat
    # frame and its index, which a process backend would pickle to every core.
    if verbose:
        logger.info({"message": "Subtracting protected areas from habitat areas..."})
    results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(process_country_habitat)(
            total_area[total_area["location"] == country].reset_index(drop=True),
            pa[pa["ISO3"] == country].reset_index(drop=True),
            habitat_gdf,
        )
        for country in tqdm(countries)
    )

    populated = [result for result in results if not result.empty]
    habitat_minus_pa = (
        pd.concat(populated).reset_index(drop=True) if populated else total_area.iloc[:0]
    )
    if verbose:
        logger.info({"message": f"Output file has {len(habitat_minus_pa)} rows."})

    # Save to GCS

    out_file = CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)
    archive_out_file = ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)

    upload_gdf(
        bucket_name=bucket,
        gdf=habitat_minus_pa,
        destination_blob_name=out_file,
    )

    upload_gdf(
        bucket_name=bucket,
        gdf=habitat_minus_pa,
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

    read_mpa = read_parquet_from_gcs if mpa_file.endswith(".parquet") else read_json_df
    mpa = read_mpa(
        bucket_name=bucket,
        filename=mpa_file,
        verbose=verbose,
    )

    location = read_json_df(
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

    # Save to GCS
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=out_file,
    )

    # Save to archive
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=archive_out_file,
    )
