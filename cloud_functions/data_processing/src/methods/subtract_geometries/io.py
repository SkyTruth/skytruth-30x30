import geopandas as gpd

from src.core.commons import add_tolerance_suffix
from src.core.params import BUCKET
from src.core.processors import filter_protected_planet
from src.utils.gcp import upload_gdf


def load_pa_by_location(
    reader,
    filename: str,
    tolerance: float,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Reads a protected areas file and shapes it for per-location subtraction.

    A PA listing several ISO3 codes is exploded into one row per location, so it is
    subtracted from every location it belongs to. Non-polygonal records are dropped
    and the remaining geometries made valid, since the difference that follows
    rejects both.

    Parameters
    ----------
    reader : callable
        GCS reader to read the file with, taking bucket_name, filename and verbose.
    filename : str
        Filename of the protected areas file, before the tolerance suffix is added.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame of valid polygonal protected areas, one row per PA per ISO3.
    """
    pa = reader(
        bucket_name=bucket,
        filename=add_tolerance_suffix(filename, tolerance),
        verbose=verbose,
    ).pipe(filter_protected_planet)

    # Create one row per location
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()
    return pa


def upload_with_archive(
    gdf: gpd.GeoDataFrame,
    out_file: str,
    archive_out_file: str,
    bucket: str = BUCKET,
):
    """
    Saves a GeoDataFrame to GCS under both its live and its archive blob name.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        GeoDataFrame to save.
    out_file : str
        Blob name the pipeline reads from.
    archive_out_file : str
        Blob name the dated copy is kept under.
    bucket : str
        GCS bucket name.
    """
    upload_gdf(
        bucket_name=bucket,
        gdf=gdf,
        destination_blob_name=out_file,
    )

    upload_gdf(
        bucket_name=bucket,
        gdf=gdf,
        destination_blob_name=archive_out_file,
    )
