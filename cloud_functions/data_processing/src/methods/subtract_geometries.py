import pandas as pd
import geopandas as gpd
from joblib import Parallel, delayed
from tqdm.auto import tqdm
from src.utils.gcp import (
    read_json_df,       # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    upload_gdf_zip,     # Saves a GeoDataFrame to GCS as a zipped file
    upload_gdf          # Saves a GeoDataFrame to GCS as a .geojson file
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

def dissolve_geometries(bucket: str,
                        gdf_file: str,
                        out_file: str,
                        tolerance: float,
                        verbose: bool = True
    ):
    """
    Loads a GeoDataFrame from GCS, dissolves geometries by country,
    and saves the output as a .geojson to GCS.

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
        GeoDataFrame saved to GCS as a GeoJSON file.
    """

    # Load GeoDataFrame from GCS
    pa = read_json_df(
        bucket_name=bucket,
        filename=gdf_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(['MultiPolygon', 'Polygon'])]
    pa.geometry = pa.geometry.make_valid()

    # Label Antarctica PAs as ABNJ (areas beyond national jurisdiction)
    pa.loc[pa["ISO3"] == "ATA", "ISO3"] = "ABNJ"

    # Dissolve geometries by unique ISO3 codes
    if verbose:
        print(f'Dissolving geometries by ISO3 codes...')
    pa["location"] = pa['ISO3'].str.split(';')
    pa = pa.explode("location", ignore_index=True)
    dissolved = pa[['location', 'geometry']].dissolve(by='location').reset_index()

    if verbose:
        print(f'Output file has {len(dissolved)} rows.')

    # Save to GCS as zipped shapefile
    upload_gdf(
        bucket_name=bucket,
        gdf=dissolved,
        destination_blob_name=out_file.replace('.geojson', f'_{tolerance}.geojson')
    )

def generate_total_area_minus_pa(bucket: str,
                                 total_area_file: str,
                                 pa_file: str,
                                 is_processed: bool,
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
        filename=total_area_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )
    total_area = total_area[['location', 'geometry']]

    # Dissolved protected areas: PA (terrestrial) or MPA (marine)
    pa = read_json_df(
        bucket_name=bucket,
        filename=pa_file.replace('.geojson', f'_{tolerance}.geojson'),
        verbose=verbose
    )

    # Get list of unique country codes
    countries = total_area['location'].unique().tolist()

    if not is_processed:
        # Keep only polygon records and make the geometries valid
        pa = pa[pa.geometry.geom_type.isin(['MultiPolygon', 'Polygon'])]
        pa.geometry = pa.geometry.make_valid()

        # Label Antarctica PAs as ABNJ (areas beyond national jurisdiction)
        pa.loc[pa["ISO3"] == "ATA", "ISO3"] = "ABNJ"

        # Dissolve country geometries by location
        if verbose:
            print(f'Dissolving {len(countries)} country geometries...')
        pa["location"] = pa['ISO3'].str.split(';')
        pa = pa.explode("location", ignore_index=True)
        pa = pa[['location', 'geometry']].dissolve(by='location').reset_index()
    
    # Subtract geometries
    if verbose:
        print(f'Subtracting protected areas from total areas...')
    results = Parallel(n_jobs=-1, backend='loky')(
        delayed(process_country)(
            total_area[total_area['location'] == country].reset_index(),
            pa[pa['location'] == country].reset_index()
        )
        for country in tqdm(countries)
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
