import geopandas as gpd
import pandas as pd
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from src.core.processors import country_wrapping
from src.utils.gcp import (
    read_json_df,                    # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    upload_gdf_zip,                  # Saves a GeoDataFrame to GCS as a zipped file
    load_zipped_shapefile_from_gcs,  # Loads a zipped shapefile from GCS into a GeoDataFrame
)
from src.utils.logger import Logger

logger = Logger()

def process_country(country_area: gpd.GeoDataFrame, 
                    country_pa: gpd.GeoDataFrame):
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
        return country_area
    country_area = country_area.copy()
    country_area['geometry'] = country_area.difference(country_pa)
    return country_area

def process_pas(pa: gpd.GeoDataFrame):
    """
    Processes protected areas GeoDataFrame by making geometries valid and dissolving by country.

    Parameters
    ----------
    pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas.

    Returns
    -------
        Processed GeoDataFrame with dissolved protected areas by country.
    """
    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(['MultiPolygon', 'Polygon'])]
    pa.geometry = pa.geometry.make_valid()

    # Split PAs with multiple country codes into separate rows
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Adjust countries as needed
    pa = country_wrapping(pa, loc_col="ISO3")

    # Dissolve geometries by country
    dissolved = pa[['ISO3', 'geometry']].dissolve(by='ISO3').reset_index()
    dissolved = dissolved[dissolved.geometry.geom_type.isin(['MultiPolygon', 'Polygon'])]

    return dissolved

def dissolve_geometries(bucket: str,
                        gdf_file: str,
                        out_file: str,
                        tolerance: float,
                        verbose: bool = True
    ):
    """
    Loads a GeoDataFrame from GCS, dissolves geometries by country,
    and saves the output to GCS.

    Parameters
    ----------
    bucket : str
        GCS bucket name.
    gdf_file : str
        Filename of GeoDataFrame GeoJSON in GCS.
    out_file : str
        Filename for output GeoJSON file in GCS.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.
    
    Returns
    -------
        GeoDataFrame saved to GCS as a zipped file.
    """

    # Load GeoDataFrame from GCS
    pa = read_json_df(
        bucket_name=bucket,
        filename=gdf_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )
    
    # Clean and dissolve geometries by country
    dissolved = process_pas(pa)
    if verbose:
        logger.info({"message": f'Dissolved file has {len(dissolved)} rows.'})

    # Save to GCS as zipped shapefile
    upload_gdf_zip(
        bucket_name=bucket,
        gdf=dissolved,
        destination_blob_name=out_file.replace('.zip', f'_{tolerance}.zip'),
        output_file_type=".shp",
    )

def generate_total_area_minus_pa(bucket: str,
                                 total_area_file: str,
                                 pa_file: str,
                                 is_processed: bool,
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
        GeoDataFrame saved to GCS as a zipped shapefile.
    """

    # Total areas: GADM (terrestrial) or EEZ (marine)
    total_area = read_json_df(
        bucket_name=bucket,
        filename=total_area_file.replace('.geojson', f"_{tolerance}.geojson"),
        verbose=verbose
    )
    total_area = total_area[['location', 'geometry']]

    # Get list of unique country codes
    countries = total_area['location'].unique().tolist()

    # Protected areas: PA (terrestrial) or MPA (marine)
    if is_processed:
        pa = load_zipped_shapefile_from_gcs(
            bucket=bucket,
            filename=pa_file.replace('.zip', f"_{tolerance}.zip")
        )
    else:
        pa = read_json_df(
            bucket_name=bucket,
            filename=pa_file.replace('.geojson', f"_{tolerance}.geojson"),
            verbose=verbose
        )
        # Clean and dissolve geometries by country
        pa = process_pas(pa)
    
    # Subtract geometries
    if verbose:
        logger.info({"message": f"Subtracting protected areas from total areas..."})
    results = Parallel(n_jobs=-1, backend='loky')(
        delayed(process_country)(
            total_area[total_area['location'] == country].reset_index(),
            pa[pa['ISO3'] == country].reset_index()
        )
        for country in tqdm(countries)
    )

    total_area_minus_pa = pd.concat(results).reset_index(drop=True)
    if verbose:
        logger.info({"message": f"Output file has {len(total_area_minus_pa)} rows."})

    # Save to GCS as zipped shapefile
    upload_gdf_zip(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
        output_file_type=".shp",
    )
