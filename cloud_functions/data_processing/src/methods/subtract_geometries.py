import pandas as pd
import geopandas as gpd
from joblib import Parallel, delayed
from tqdm.auto import tqdm
from src.utils.gcp import (
    read_json_df,       # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    upload_gdf_zip      # Saves a GeoDataFrame to GCS as a zipped file
)
from src.utils.logger import Logger

logger = Logger()

def process_country(data_tuple: tuple):
    """
    Subtracts protected areas from total area for a country.

    Parameters
    ----------
    data_tuple : tuple
        A tuple containing (country_area, country_pa).

    Returns
    -------
        GeoDataFrame with protected areas subtracted from total area for a country.
    """
    country_area, country_pa = data_tuple
    if country_pa is None:
        return country_area
    country_area = country_area.copy()
    country_area['geometry'] = country_area.geometry.difference(country_pa)
    return country_area

def generate_total_area_minus_pa(bucket: str, 
                                 total_area_file: str, 
                                 pa_file: str, 
                                 out_file: str, 
                                 tolerance: float, 
                                 verbose: bool = True
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
        filename=total_area_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )
    total_area = total_area[['location', 'geometry']]

    # Protected areas: PA (terrestrial) or MPA (marine)
    pa = read_json_df(
        bucket_name=bucket,
        filename=pa_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(['MultiPolygon', 'Polygon'])]
    pa.geometry = pa.geometry.make_valid()

    # Label Antarctica PAs as ABNJ (areas beyond national jurisdiction)
    pa.loc[pa["ISO3"] == "ATA", "ISO3"] = "ABNJ"

    # Create country-specific subsets
    countries = total_area['location'].unique().tolist()
    if verbose:
        print(f'Dissolving {len(countries)} country geometries...')
    country_data = [
        (total_area[total_area['location'] == country],
        pa[pa['ISO3'] == country].union_all() if not pa[pa['ISO3'] == country].empty else None)
        for country in countries
    ]

    # Subtract PAs from total areas in parallel
    if verbose:
        print(f'Subtracting protected areas from total areas...')
    results = Parallel(n_jobs=-1)(
        delayed(process_country)(data) for data in tqdm(country_data)
    )

    total_area_minus_pa = pd.concat(results).reset_index(drop=True)
    if verbose:
        print(f'Output file has {len(total_area_minus_pa)} rows.')

    # Save to GCS as zipped shapefile
    upload_gdf_zip(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
        output_file_type='.shp'
    )
