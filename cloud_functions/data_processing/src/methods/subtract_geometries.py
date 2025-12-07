import pandas as pd
import geopandas as gpd
import shapely
from shapely.geometry import GeometryCollection
from src.utils.gcp import (
    read_json_df,       # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame.
    upload_gdf_zip      # Saves a GeoDataFrame to GCS as a .geojson file.
)
from src.utils.logger import Logger

logger = Logger()

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

    # Dissolve PAs per country
    if verbose:
        print('Dissolving protected areas by country...')
    pa_union = (
        pa.groupby("ISO3", sort=False)["geometry"]
        .agg(lambda arr: shapely.union_all(arr.values))
        .rename("pa_geom")
        .reset_index()
    )

    # Join PAs to total areas
    total_area_minus_pa = total_area.merge(pa_union, left_on="location", right_on="ISO3", how="left")
    
    # Subtract PAs from total area per country
    if verbose:
        print('Subtracting protected areas from total areas...')
    total_area_minus_pa["geometry"] = shapely.difference(
        total_area_minus_pa["geometry"].values, 
        total_area_minus_pa["pa_geom"].fillna(GeometryCollection()).values
    )

    # Filter columns
    total_area_minus_pa = total_area_minus_pa[['location', 'geometry']]
    if verbose:
        print(f'Output file has {len(total_area_minus_pa)} rows.')

    # Save to GCS as zipped shapefile
    upload_gdf_zip(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
        output_file_type='.shp'
    )
