import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from src.utils.gcp import (
    read_json_df,
    upload_gdf_zip,
)
from src.utils.logger import Logger

logger = Logger()


def process_country(country: str, boundary_gdf: gpd.GeoDataFrame, pa_gdf: gpd.GeoDataFrame):
    """
    Subtracts the protected area from the total area and returns a GeoDataFrame.

    Parameters
    ----------
    country : str
        Country name (3-letter abbreviation).
    boundary_gdf : gpd.GeoDataFrame
        Total areas GeoDataFrame.
    pa_gdf : gpd.GeoDataFrame
        Protected areas GeoDataFrame.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame of boundary_gdf with pa_gdf subtracted, retaining the original
            fields of boundary_gdf.
    """
    try:
        country_area = boundary_gdf[boundary_gdf["location"] == country]
        country_pa = pa_gdf[pa_gdf["ISO3"].str.contains(country)].dissolve()
        if country_pa.empty:
            # If no protected areas, return original boundary
            return country_area
        else:
            # If protected areas found, return original boundary with protected areas removed
            return country_area.overlay(country_pa, how="difference")

    except Exception as e:
        logger.warning({"message": f"Error processing {country}: {e}"})
        return None


def generate_total_area_minus_pa(
    bucket: str,
    total_area_file: str,
    pa_file: str,
    out_file: str,
    tolerance: float,
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
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a zipped shapefile.
    """

    # Total areas: GADM (terrestrial) or EEZ (marine)
    total_area = read_json_df(
        bucket_name=bucket,
        filename=total_area_file.replace(".geojson", f"_{tolerance}.geojson"),
        verbose=verbose,
    )
    # Protected areas: PA (terrestrial) or MPA (marine)
    pa = read_json_df(
        bucket_name=bucket,
        filename=pa_file.replace(".geojson", f"_{tolerance}.geojson"),
        verbose=verbose,
    )

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])]
    pa.geometry = pa.geometry.make_valid()

    # Subtract protected areas from each country in parallel
    countries = total_area["location"].unique().tolist()
    results = Parallel(n_jobs=4, backend="loky")(
        delayed(process_country)(country, total_area, pa) for country in tqdm(countries)
    )
    total_area_minus_pa = pd.concat(results).reset_index()

    if verbose:
        print(f"Output file has {len(total_area_minus_pa)} rows.")

    # Save to GCS as zipped shapefile
    upload_gdf_zip(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
        output_file_type=".shp",
    )
