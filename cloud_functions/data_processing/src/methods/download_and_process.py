from io import BytesIO

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import MultiPoint, Point

from src.core.commons import (
    download_and_duplicate_zipfile,
    download_mpatlas_zone,
)
from src.core.params import (
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    BUCKET,
    CHUNK_SIZE,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_URL,
    PP_API_KEY,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    TOLERANCES,
    WDPA_API_URL,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_MARINE_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
    WDPA_URL,
    today_formatted,
)
from src.core.processors import clean_geometries
from src.utils.gcp import (
    duplicate_blob,
    load_gdb_layer_from_gcs,
    upload_dataframe,
    upload_gdf,
)


def download_mpatlas_country(
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    current_filename: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    upload_dataframe(bucket, pd.DataFrame(data), archive_filename, project_id=project, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_mpatlas(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    project: str = PROJECT,
    mpatlas_filename: str = MPATLAS_FILE_NAME,
    archive_mpatlas_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    mpatlas_country_url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    mpatlas_country_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_mpatlas_country_file_name: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    verbose: bool = True,
) -> None:
    download_mpatlas_country(
        bucket,
        project,
        mpatlas_country_url,
        mpatlas_country_file_name,
        archive_mpatlas_country_file_name,
    )

    download_mpatlas_zone(
        url,
        bucket,
        mpatlas_filename,
        archive_mpatlas_filename,
        verbose,
    )


def download_protected_seas(
    url: str = PROTECTED_SEAS_URL,
    bucket: str = BUCKET,
    filename: str = PROTECTED_SEAS_FILE_NAME,
    archive_filename: str = ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    project: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Downloads Protected Seas data from the provided URL, processes it into a DataFrame,
    and uploads both a current version and an archived version to Google Cloud Storage.

    Parameters:
    ----------
    url : str
        The URL to fetch the Protected Seas data from.
    bucket : str
        GCS bucket name where the data will be saved.
    filename : str
        Blob name for the current, active version of the data.
    archive_filename : str
        Blob name for the archived version of the data.
    project : str
        Google Cloud project ID used for authentication during upload.
    verbose : bool, optional
        If True, prints progress and status messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()

    data = pd.DataFrame(response.json())

    data["includes_multi_jurisdictional_areas"] = data["includes_multi_jurisdictional_areas"].map(
        {"t": True, "f": False}
    )

    if verbose:
        print(f"saving Protected Seas to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_protected_planet_global(
    current_filename: str,
    archive_filename: str,
    project_id: str = PROJECT,
    url: str = WDPA_GLOBAL_LEVEL_URL,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads the Global Protected Planet statistics CSV from the specified URL,
    uploads it to Google Cloud Storage, and stores both an archived and current version.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the primary/current version of the data.
    archive_filename : str
        GCS blob name for the archived version of the data.
    project_id : str, optional
        Google Cloud project ID used for authentication. Defaults to `PROJECT`.
    url : str, optional
        URL to download the global statistics CSV. Defaults to `WDPA_GLOBAL_LEVEL_URL`.
    bucket : str, optional
        GCS bucket name where the file will be saved. Defaults to `BUCKET`.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()
    data = pd.read_csv(BytesIO(response.content))

    if verbose:
        print(f"saving Global Protected Planet statistics to to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project_id, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet_country(
    current_filename: str,
    archive_filename: str,
    pp_api_key: str,
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = WDPA_API_URL,
    per_page: int = 50,
    verbose: bool = True,
) -> None:
    """
    Downloads country-level statistics from the Protected Planet API,
     compiles all paginated results, and uploads the data to Google Cloud Storage
     as both a current and archived file.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the latest, actively used version of the data.
    archive_filename : str
        GCS blob name for the archived backup copy of the data.
    pp_api_key : str
        Protected Planet API token for authenticated requests.
    bucket : str, optional
        Name of the GCS bucket to upload data to. Defaults to `BUCKET`.
    project : str, optional
        Google Cloud project ID used during upload. Defaults to `PROJECT`.
    url : str, optional
        Base URL of the Protected Planet API. Defaults to `WDPA_API_URL`.
    per_page : int, optional
        Number of results to fetch per API page. Default is 50.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """

    def fetch_data(params):
        response = requests.get(f"{url}/countries", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("countries", [])

    page = 1
    params = {"token": pp_api_key, "per_page": per_page, "page": page}
    all_areas = []

    results = fetch_data(params)
    while results:
        if verbose:
            print(f"Fetching page {page}...")

        all_areas.extend(results)
        page += 1
        params = {"token": pp_api_key, "per_page": per_page, "page": page}
        results = fetch_data(params)

    if verbose:
        print(f"Uploading {len(all_areas)} protected areas to gs://{bucket}/{archive_filename}")

    upload_dataframe(
        bucket, pd.DataFrame(all_areas), archive_filename, project_id=project, verbose=True
    )
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet(
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    archive_wdpa_global_level_file_name: str = ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    archive_wdpa_country_level_file_name: str = ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    pp_api_key: str = PP_API_KEY,
    project_id: str = PROJECT,
    wdpa_global_url: str = WDPA_GLOBAL_LEVEL_URL,
    wdpa_url: str = WDPA_URL,
    api_url: str = WDPA_API_URL,
    wdpa_file_name: str = WDPA_FILE_NAME,
    archive_wdpa_file_name: str = ARCHIVE_WDPA_FILE_NAME,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads and processes data from Protected Planet, including:
    - The main WDPA ZIP archive
    - Global-level protected area statistics
    - Country-level protected area statistics

    All datasets are stored in Google Cloud Storage with both current and archived versions.

    Parameters:
    ----------
    wdpa_global_level_file_name : str
        GCS blob name for the current global statistics file.
    archive_wdpa_global_level_file_name : str
        GCS blob name for the archived global statistics file.
    wdpa_country_level_file_name : str
        GCS blob name for the current country statistics file.
    archive_wdpa_country_level_file_name : str
        GCS blob name for the archived country statistics file.
    pp_api_key : str
        Protected Planet API token for accessing country-level stats.
    project_id : str
        Google Cloud project ID used for uploads.
    wdpa_global_url : str
        URL for the global statistics CSV.
    wdpa_url : str
        URL for the WDPA ZIP file.
    api_url : str
        URL for the Protected Planet API (used for country-level stats).
    wdpa_file_name : str
        GCS blob name for the current WDPA ZIP file.
    archive_wdpa_file_name : str
        GCS blob name for the archived WDPA ZIP file.
    bucket : str
        Name of the GCS bucket to upload all files to.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """
    # download wdpa
    download_and_duplicate_zipfile(
        wdpa_url,
        bucket,
        wdpa_file_name,
        archive_wdpa_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )

    # download wdpa global stats
    download_protected_planet_global(
        wdpa_global_level_file_name,
        archive_wdpa_global_level_file_name,
        project_id=project_id,
        url=wdpa_global_url,
        bucket=bucket,
    )

    # download wdpa country stats
    download_protected_planet_country(
        wdpa_country_level_file_name,
        archive_wdpa_country_level_file_name,
        pp_api_key,
        bucket=bucket,
        project=project_id,
        url=api_url,
        per_page=50,
        verbose=verbose,
    )


def process_protected_area_geoms(
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    wdpa_file_name: str = WDPA_FILE_NAME,
    bucket: str = BUCKET,
    tolerances: list | tuple = TOLERANCES,
    verbose: bool = True,
):
    def create_buffer(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        def calculate_radius(rep_area: float) -> float:
            return ((rep_area * 1e6) / np.pi) ** 0.5

        df = df.to_crs("ESRI:54009")
        df["geometry"] = df.apply(
            lambda row: row.geometry.buffer(calculate_radius(row["REP_AREA"])),
            axis=1,
        )
        return df.to_crs("EPSG:4326").copy()

    if verbose:
        print(f"loading PAs from gs://{bucket}/{wdpa_file_name}")

    wdpa = load_gdb_layer_from_gcs(
        wdpa_file_name,
        bucket,
        layers=[f"WDPA_poly_{today_formatted}", f"WDPA_point_{today_formatted}"],
    )

    if verbose:
        print("buffering and simplifying geometries")

    # TODO: This eliminates point PAs that have REP_AREA=0,
    # is this what we want?: TECH-3163
    point_pas = wdpa[wdpa.geometry.apply(lambda geom: isinstance(geom, (Point, MultiPoint)))]
    point_pas = point_pas[point_pas["REP_AREA"] > 0].copy()
    buffered_point_pas = create_buffer(point_pas)
    buffered_point_pas = buffered_point_pas[buffered_point_pas.geometry.is_valid]
    poly_pas = wdpa[~wdpa.geometry.apply(lambda geom: isinstance(geom, (Point, MultiPoint)))]
    wdpa = pd.concat((poly_pas, buffered_point_pas), axis=0).pipe(clean_geometries)

    for tolerance in tolerances:
        df = wdpa.copy()

        if verbose:
            print(f"simplifying PAs with tolerance = {tolerance}")
        if tolerance is not None:
            df["geometry"] = df["geometry"].simplify(tolerance=tolerance)

        df["geometry"] = df["geometry"].make_valid()

        if verbose:
            print("separating marine and terrestrial PAs")
        wdpa_ter = df[df["MARINE"].eq("0")].copy()
        wdpa_ter = wdpa_ter.dropna(axis=1, how="all")
        wdpa_mar = df[df["MARINE"].isin(["1", "2"])].copy()
        wdpa_mar = wdpa_mar.dropna(axis=1, how="all")

        ter_out_fn = terrestrial_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving terrestrial PAs to {ter_out_fn}")
        upload_gdf(bucket, wdpa_ter, ter_out_fn)

        mar_out_fn = marine_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving marine PAs to {mar_out_fn}")
        upload_gdf(bucket, wdpa_mar, mar_out_fn)

    return wdpa
