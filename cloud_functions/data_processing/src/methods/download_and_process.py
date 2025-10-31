import glob
import os
import shutil
import zipfile
from io import BytesIO

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import MultiPoint, Point, shape

from src.core.commons import (
    download_file_with_progress,
    download_mpatlas_zone,
    print_peak_memory_allocation,
    unzip_file,
)
from src.core.params import (
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    BUCKET,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    MPATLAS_URL,
    PP_API_KEY,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    TOLERANCES,
    WDPA_API_URL,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_MARINE_FILE_NAME,
    WDPA_META_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
    WDPA_URL,
)
from src.core.processors import calculate_area, choose_pa_area
from src.utils.gcp import (
    duplicate_blob,
    read_json_from_gcs,
    upload_dataframe,
    upload_gdf,
)
from src.utils.logger import Logger

logger = Logger()


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
    meta_file_name: str = MPATLAS_META_FILE_NAME,
    archive_mpatlas_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    mpatlas_country_url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    mpatlas_country_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_mpatlas_country_file_name: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    verbose: bool = True,
    project_id: str = PROJECT,
) -> None:
    def safe_shape(geom):
        try:
            return shape(geom) if geom else None
        except Exception:
            return None

    download_mpatlas_country(
        bucket=bucket,
        project=project,
        url=mpatlas_country_url,
        current_filename=mpatlas_country_file_name,
        archive_filename=archive_mpatlas_country_file_name,
    )

    download_mpatlas_zone(
        url=url,
        bucket=bucket,
        filename=mpatlas_filename,
        archive_filename=archive_mpatlas_filename,
        verbose=verbose,
    )

    if verbose:
        print(f"loading MPAtlas from {mpatlas_filename}")
    mpa = read_json_from_gcs(bucket, mpatlas_filename)

    mpa_all = gpd.GeoDataFrame(
        [
            {**feat["properties"], "geometry": safe_shape(feat.get("geometry"))}
            for feat in mpa["features"]
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    # add area column
    if verbose:
        print("calculating MPA area (calculated_area_km2)")
    mpa_all = calculate_area(mpa_all, output_area_column="calculated_area_km2")

    # add bounding box column
    if verbose:
        print("calculating MPA bounding box (bbox)")
    mpa_all["bbox"] = mpa_all.geometry.apply(lambda g: g.bounds if g is not None else None)

    # Upload metadata (no geometry)
    if verbose:
        print(f"saving metadata to {meta_file_name}")
    upload_dataframe(
        bucket,
        mpa_all.drop(columns="geometry"),
        meta_file_name,
        project_id=project_id,
        verbose=verbose,
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
    data = data.drop_duplicates()

    if verbose:
        print(f"saving Protected Seas to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def process_protected_area_geoms(
    wdpa: gpd.GeoDataFrame,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
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

    def buffer_if_point(row, crs):
        g = row.geometry
        if isinstance(g, (Point, MultiPoint)) and row.REP_AREA > 0:
            # build a 1-row GeoDataFrame with the same CRS
            row_gdf = gpd.GeoDataFrame(
                row.to_frame().T,
                geometry="geometry",
                crs=crs,  # 1-row DataFrame
            )
            buffed = create_buffer(row_gdf)  # your existing function
            return buffed.geometry.iloc[0]
        return g

    def save_simplified_marine_terrestrial_pas(
        df, tolerance, terrestrial_pa_file_name, marine_pa_file_name
    ):
        df = df.copy()

        if verbose:
            print(f"simplifying PAs with tolerance = {tolerance}")

        if tolerance is not None:
            df["geometry"] = df["geometry"].simplify(tolerance=tolerance)

        df = df.dropna(axis=1, how="all")

        ter_out_fn = terrestrial_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving and duplicating terrestrial PAs to {ter_out_fn}")
        upload_gdf(bucket, df[df["MARINE"].eq("0")], ter_out_fn)
        duplicate_blob(bucket, ter_out_fn, f"archive/{ter_out_fn}", verbose=verbose)

        mar_out_fn = marine_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving and duplicating marine PAs to {mar_out_fn}")
        upload_gdf(bucket, df[df["MARINE"].isin(["1", "2"])], mar_out_fn)
        duplicate_blob(bucket, mar_out_fn, f"archive/{mar_out_fn}", verbose=verbose)

    if verbose:
        print("buffering and simplifying geometries")

    wdpa["geometry"] = wdpa.apply(lambda r: buffer_if_point(r, wdpa.crs), axis=1)
    wdpa = wdpa.loc[wdpa.geometry.is_valid]

    for tolerance in tolerances:
        _ = print_peak_memory_allocation(
            save_simplified_marine_terrestrial_pas,
            wdpa,
            tolerance,
            terrestrial_pa_file_name,
            marine_pa_file_name,
        )


def unpack_pas(pa_dir, verbose):
    to_append = []
    for zip_path in glob.glob(os.path.join(pa_dir, "*.zip")):
        with zipfile.ZipFile(zip_path) as z:
            shp_paths = [n for n in z.namelist() if n.lower().endswith(".shp")]

            for shp in shp_paths:
                print(f"Loading layer: {shp}")
                gdf = gpd.read_file(f"zip://{zip_path}!{shp}")
                gdf["layer_name"] = shp.replace(".shp", "")
                to_append.append(gdf)
        try:
            os.remove(zip_path)
            if verbose:
                print(f"Deleted {zip_path}")
        except Exception as excep:
            logger.warning(
                {"message": f"Warning: failed to delete {zip_path}", "error": str(excep)}
            )

    if not to_append:
        raise ValueError(f"No shapefiles found in {pa_dir}")
    return pd.concat(to_append, axis=0)


def download_and_process_protected_planet_pas(
    wdpa_url: str = WDPA_URL,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    meta_file_name: str = WDPA_META_FILE_NAME,
    tolerances: list | tuple = TOLERANCES,
    verbose: bool = True,
    bucket: str = BUCKET,
    project_id: str = PROJECT,
):
    dir = "/tmp"
    os.makedirs(dir, exist_ok=True)

    base_zip_path = os.path.join(dir, "wdpa.zip")
    pa_dir = os.path.join(dir, "wdpa")

    if verbose:
        print(f"downloading {wdpa_url}")
    _ = print_peak_memory_allocation(download_file_with_progress, wdpa_url, base_zip_path)

    if verbose:
        print(f"unzipping {base_zip_path}")
    _ = print_peak_memory_allocation(unzip_file, base_zip_path, pa_dir)

    if verbose:
        print(f"unpacking PAs from {pa_dir}")
    pas = print_peak_memory_allocation(unpack_pas, pa_dir, verbose)

    try:
        shutil.rmtree(pa_dir)
        if verbose:
            print(f"Deleted directory {pa_dir}")

    except Exception as excep:
        logger.warning({
            "message": f"Warning: failed to delete directory {pa_dir}",
            "error": str(excep)
        })

    if verbose:
        print("adding bbox and area columns")

    pas["bbox"] = pas.geometry.apply(lambda g: g.bounds if g is not None else None)
    pas = choose_pa_area(pas)

    if verbose:
        print(f"saving wdpa metadata to {meta_file_name}")
    upload_dataframe(
        bucket, pas.drop(columns="geometry"), meta_file_name, project_id=project_id, verbose=verbose
    )

    if verbose:
        print("processing protected areas")
    process_protected_area_geoms(
        pas,
        terrestrial_pa_file_name=terrestrial_pa_file_name,
        marine_pa_file_name=marine_pa_file_name,
        bucket=bucket,
        tolerances=tolerances,
        verbose=verbose,
    )


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
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    tolerances: list | tuple = TOLERANCES,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads and processes data from Protected Planet, including:
    - Terrestrial and Marine protected areas
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
    terrestrial_pa_file_name : str
        Root of GCS blob name for terrestrial protected areas.
    marine_pa_file_name : str
        Root of GCS blob name for marine protected areas.
    tolerances: list
        Tolerances to simplify geometries by for further processing.
    bucket : str
        Name of the GCS bucket to upload all files to.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """
    # download wdpa
    download_and_process_protected_planet_pas(
        wdpa_url=wdpa_url,
        terrestrial_pa_file_name=terrestrial_pa_file_name,
        marine_pa_file_name=marine_pa_file_name,
        tolerances=tolerances,
        verbose=verbose,
        bucket=bucket,
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
