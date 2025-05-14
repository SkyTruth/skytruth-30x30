from flask import Request
from io import BytesIO
import os
import pandas as pd
import requests
from typing import Tuple

from params import (
    CHUNK_SIZE,
    MARINE_REGIONS_URL,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    EEZ_ZIPFILE_NAME,
    EEZ_PARAMS,
    HIGH_SEAS_ZIPFILE_NAME,
    HIGH_SEAS_PARAMS,
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
    ARCHIVE_HABITATS_FILE_NAME,
    SEAMOUNTS_URL,
    SEAMOUNTS_FILE_NAME,
    ARCHIVE_SEAMOUNTS_FILE_NAME,
)
from utils.gcp import (
    save_file_bucket,
    duplicate_blob,
    download_zip_to_gcs,
    upload_dataframe,
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


def main(request: Request) -> Tuple[str, int]:
    """
    Cloud Function entry point that dispatches behavior based on the 'METHOD' key
    in the incoming HTTP request body. Each METHOD corresponds to a specific data
    download task, often writing to Google Cloud Storage.

    The function expects a JSON body with a `METHOD` key. Supported METHOD values include:

    - "dry_run": Simple test mode, prints confirmation only
    - "download_eezs": Downloads EEZ shapefiles from Marine Regions API
    - "download_high_seas": Downloads high seas shapefiles from Marine Regions API
    - "download_habitats": Downloads and stores habitat and seamount shapefiles
    - "download_mpatlas": Downloads MPAtlas dataset and stores current + archive versions
    - "download_protected_seas": Downloads Protected Seas JSON data and uploads it
    - "download_protected_planet_wdpa": Downloads full Protected Planet suite (WDPA ZIP + stats)

    Unsupported methods will trigger a warning message.

    Parameters:
    ----------
    request : flask.Request
        The incoming HTTP request. Must include a JSON body with a 'METHOD' key.

    Returns:
    -------
    Tuple[str, int]
        A tuple of ("OK", 200) to signal successful completion to the client.
    """

    try:
        data = request.get_json(silent=True) or {}
        method = data.get("METHOD", "default")

        match method:
            case "dry_run":
                print("Dry Run Complete!")

            case "download_eezs":
                download_zip_to_gcs(
                    MARINE_REGIONS_URL,
                    BUCKET,
                    EEZ_ZIPFILE_NAME,
                    data=MARINE_REGIONS_BODY,
                    params=EEZ_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_high_seas":
                download_zip_to_gcs(
                    MARINE_REGIONS_URL,
                    BUCKET,
                    HIGH_SEAS_ZIPFILE_NAME,
                    data=MARINE_REGIONS_BODY,
                    params=HIGH_SEAS_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_habitats":
                download_habitats(
                    habitats_url=HABITATS_URL,
                    habitats_file_name=HABITATS_FILE_NAME,
                    archive_habitats_file_name=ARCHIVE_HABITATS_FILE_NAME,
                    seamounts_url=SEAMOUNTS_URL,
                    seamounts_file_name=SEAMOUNTS_FILE_NAME,
                    archive_seamounts_file_name=ARCHIVE_SEAMOUNTS_FILE_NAME,
                    bucket=BUCKET,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_habitats":
                download_habitats(verbose=verbose)

            case "download_mpatlas":
                download_mpatlas(verbose=verbose)

            case "download_protected_seas":
                download_protected_seas(verbose=verbose)

            case "download_protected_planet_wdpa":
                download_protected_planet(verbose=verbose)

            case _:
                print(f"METHOD: {method} not a valid option")

        print("Process complete!")

        return "OK", 200
    except Exception as e:
        print(f"METHOD {method} failed: {e}")

        return f"Internal Server Error: {e}", 500
