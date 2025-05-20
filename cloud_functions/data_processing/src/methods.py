from io import BytesIO
import os
import pandas as pd
import requests
import gcsfs
import zipfile
import io

from src.params import (
    CHUNK_SIZE,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_URL,
    MPATLAS_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    WDPA_API_URL,
    WDPA_URL,
    WDPA_FILE_NAME,
    ARCHIVE_WDPA_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    HABITATS_URL,
    HABITATS_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    ARCHIVE_HABITATS_FILE_NAME,
    SEAMOUNTS_URL,
    SEAMOUNTS_FILE_NAME,
    ARCHIVE_SEAMOUNTS_FILE_NAME,
)
from src.utils.gcp import (
    download_zip_to_gcs,
    duplicate_blob,
    load_gdb_layer_from_gcs,
    load_zipped_shapefile_from_gcs,
    save_file_bucket,
    upload_dataframe,
)

from utils.processors import (
    add_constants,
    add_environment,
    add_simplified_name,
    add_year,
    calculate_area,
    remove_columns,
    remove_non_designated_m,
    remove_non_designated_p,
)

verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")


def download_and_duplicate_zipfile(
    url: str,
    bucket: str,
    blob_name: str,
    archive_blob_name: str,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads a ZIP file from a URL and stores it in Google Cloud Storage,
    then creates a duplicate of the uploaded blob within the same GCS bucket.

    Parameters:
    ----------
    url : str
        Public or authenticated URL pointing to the ZIP file to download.
    bucket : str
        Name of the GCS bucket where the file will be stored.
    blob_name : str
        Name of the target blob to be created as a duplicate.
    archive_blob_name : str
        Name of the original blob that receives the downloaded ZIP content.
    chunk_size : int, optional
        Size (in bytes) of each chunk used during the download/upload process.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """
    if verbose:
        print(f"downloading {url} to gs://{bucket}/{archive_blob_name}")
    download_zip_to_gcs(url, bucket, archive_blob_name, chunk_size=chunk_size, verbose=verbose)
    duplicate_blob(bucket, archive_blob_name, blob_name, verbose=True)


def download_mpatlas(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    filename: str = MPATLAS_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    verbose: bool = True,
) -> None:
    """
    Downloads the MPAtlas Zone Assessment dataset from a specified URL,
    saves it to a Google Cloud Storage bucket, and duplicates the blob.

    Parameters:
    ----------
    url : str
        URL of the MPAtlas Zone Assessment file to download.
    bucket : str
        Name of the GCS bucket where the file should be stored.
    filename : str
        GCS blob name for the primary reference copy of the file.
    archive_filename : str
        GCS blob name for the archived/original version of the file.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    if verbose:
        print(f"downloading MPAtlas Zone Assessment from {url}")

    response = requests.get(url)
    response.raise_for_status()

    if verbose:
        print(f"saving MPAtlas Zone Assessment to gs://{bucket}/{archive_filename}")
    save_file_bucket(
        response.content,
        response.headers.get("Content-Type"),
        archive_filename,
        bucket,
        verbose=verbose,
    )
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


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


def download_habitats(
    habitats_url: str = HABITATS_URL,
    habitats_file_name: str = HABITATS_FILE_NAME,
    archive_habitats_file_name: str = ARCHIVE_HABITATS_FILE_NAME,
    seamounts_url: str = SEAMOUNTS_URL,
    seamounts_file_name: str = SEAMOUNTS_FILE_NAME,
    archive_seamounts_file_name: str = ARCHIVE_SEAMOUNTS_FILE_NAME,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads habitat-related datasets (habitats and seamounts) and uploads them to GCS
    as both current and archived versions.

    Parameters:
    ----------
    habitats_url : str
        URL to download the general habitat ZIP file.
    habitats_file_name : str
        GCS blob name for the current habitat dataset.
    archive_habitats_file_name : str
        GCS blob name for the archived habitat dataset.
    seamounts_url : str
        URL to download the seamounts ZIP file.
    seamounts_file_name : str
        GCS blob name for the current seamounts dataset.
    archive_seamounts_file_name : str
        GCS blob name for the archived seamounts dataset.
    bucket : str
        Name of the GCS bucket where all files will be uploaded.
    chunk_size : int, optional
        Size in bytes of each chunk used during download.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    # download habitats
    download_and_duplicate_zipfile(
        habitats_url,
        bucket,
        habitats_file_name,
        archive_habitats_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )

    # download mangroves
    # TODO: Add this

    # download seamounts
    download_and_duplicate_zipfile(
        seamounts_url,
        bucket,
        seamounts_file_name,
        archive_seamounts_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )


def generate_prptected_areas_table(
    wdpa_file_name: str = WDPA_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_FILE_NAME,
    bucket: str = BUCKET,
):
    wdpa = load_gdb_layer_from_gcs(wdpa_file_name, bucket)

    wdpa_dict = {
        "NAME": "name",
        "GIS_AREA": "area",
        "STATUS": "STATUS",
        "STATUS_YR": "year",
        "WDPAID": "wdpa_id",
        "DESIG_TYPE": "designation",
        "ISO3": "iso_3",
        "IUCN_CAT": "iucn_category",
        "MARINE": "MARINE",
        "PARENT_ISO3": "parent_id",
        "geometry": "geometry",
    }
    cols = [i for i in wdpa_dict]

    wdpa_pa = (
        wdpa[cols]
        .rename(columns=wdpa_dict)
        .pipe(remove_non_designated_p)
        .pipe(add_simplified_name)
        .pipe(add_environment)
        .pipe(add_constants, {"data_source": "Protected Planet"})
        .pipe(remove_columns, ["STATUS", "MARINE"])
    )

    mpatlas = load_zipped_shapefile_from_gcs(mpatlas_file_name, bucket)

    mpa_dict = {
        "name": "name",
        "designated_date": "designated_date",
        "wdpa_id": "wdpa_id",
        "designation": "designation",
        "establishment_stage": "mpaa_establishment_stage",
        "sovereign": "location",
        "protection_mpaguide_level": "mpaa_protection_level",
        "geometry": "geometry",
    }
    cols = [i for i in mpa_dict]
    mpa_pa = (
        mpatlas[cols]
        .rename(columns=mpa_dict)
        .pipe(add_simplified_name)
        .pipe(remove_non_designated_m)
        .pipe(add_year)
        .pipe(add_constants, {"environment": "marine", "data_source": "MPATLAS"})
        .pipe(remove_columns, "designated_date")
        .pipe(calculate_area)
    )

    return wdpa_pa, mpa_pa


def generate_habitats_table(
    habitats_file_name: str = HABITATS_ZIP_FILE_NAME,
    file_name_out: str = HABITATS_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
):
    habitats = ["warmwatercorals", "coldwatercorals", "seagrasses", "saltmarshes"]

    fs = gcsfs.GCSFileSystem()
    gcs_path = f"gs://{bucket}/{habitats_file_name}"

    # Download zipfile from GCS into memory
    with fs.open(gcs_path, "rb") as f:
        zip_bytes = f.read()

    dfs = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in habitats:
            with zf.open(f"Ocean+HabitatsDownload_Global/{name}.csv") as csv_file:
                dfs[name] = pd.read_csv(csv_file)

    marine_habitats = pd.DataFrame()
    for habitat in habitats:
        tmp = dfs[habitat][["ISO3", "protected_area", "total_area"]].copy()
        tmp["environment"] = "marine"
        tmp["habitat"] = habitat
        marine_habitats = pd.concat((marine_habitats, tmp))

    # TODO: Add Mangroves and Sea Mounts

    upload_dataframe(bucket, marine_habitats, file_name_out, project_id=project, verbose=True)
