from io import BytesIO
import os
import pandas as pd
import requests
import time

from params import (
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
    url, bucket, blob_name, archive_blob_name, chunk_size=8192, verbose=True
):
    if verbose:
        print(f"downloading {url} to gs://{bucket}/{archive_blob_name}")
    download_zip_to_gcs(url, bucket, archive_blob_name, chunk_size=chunk_size, verbose=verbose)
    duplicate_blob(bucket, archive_blob_name, blob_name, verbose=True)


def download_eezs(blob_name=EEZ_ZIPFILE_NAME, verbose=True):
    """
    Downloads eez polygon zipfile from Marine Regions
    """
    download_zip_to_gcs(
        MARINE_REGIONS_URL,
        BUCKET,
        blob_name,
        data=MARINE_REGIONS_BODY,
        params=EEZ_PARAMS,
        headers=MARINE_REGIONS_HEADERS,
        chunk_size=8192,
        verbose=verbose,
    )


def download_high_seas(blob_name=HIGH_SEAS_ZIPFILE_NAME, verbose=True):
    """
    Downloads High Seas polygon zipfile from Marine Regions
    """
    download_zip_to_gcs(
        MARINE_REGIONS_URL,
        BUCKET,
        blob_name,
        data=MARINE_REGIONS_BODY,
        params=HIGH_SEAS_PARAMS,
        headers=MARINE_REGIONS_HEADERS,
        chunk_size=8192,
        verbose=verbose,
    )


def download_mpatlas(
    url=MPATLAS_URL,
    bucket=BUCKET,
    filename=MPATLAS_FILE_NAME,
    archive_filename=ARCHIVE_MPATLAS_FILE_NAME,
    verbose=True,
):
    if verbose:
        print(f"downloading MPAtlas Zone Assessment from {url}")

    r = requests.get(url)
    r.raise_for_status()

    print(f"saving MPAtlas Zone Assessment to gs://{bucket}/{archive_filename}")
    # gdf = gpd.read_file(BytesIO(r.content))
    # save_gdf_to_zipped_shapefile_gcs(gdf, filename, bucket, filename, verbose=True)
    save_file_bucket(
        r.content, r.headers.get("Content-Type"), archive_filename, bucket, verbose=verbose
    )
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_protected_seas(
    url=PROTECTED_SEAS_URL,
    bucket=BUCKET,
    filename=PROTECTED_SEAS_FILE_NAME,
    archive_filename=ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    project=PROJECT,
    verbose=True,
):
    """
    Download Protected Seas data from website and saves zipfile to a current
    file for calculations as well as an archive file
    """
    r = requests.get(url)
    r.raise_for_status()

    data = pd.DataFrame(r.json())

    data["includes_multi_jurisdictional_areas"] = data["includes_multi_jurisdictional_areas"].map(
        {"t": True, "f": False}
    )

    print(f"saving Protected Seas to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_protected_planet_global(
    current_filename, archive_filename, project_id=PROJECT, url=WDPA_GLOBAL_LEVEL_URL, bucket=BUCKET
):
    response = requests.get(url)
    response.raise_for_status()
    data = pd.read_csv(BytesIO(response.content))

    upload_dataframe(bucket, data, archive_filename, project_id=project_id, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet_country(
    current_filename,
    archive_filename,
    pp_api_key,
    val="countries",
    bucket=BUCKET,
    project=PROJECT,
    url=WDPA_API_URL,
    per_page=50,
    verbose=True,
):
    """
    Download country level stats from Protected Planet API and saves to a current
    file for calculations as well as an archive file
    """
    page = 1
    all_areas = []
    while True:
        if verbose:
            print(f"Fetching page {page}...")
        params = {"token": pp_api_key, "per_page": per_page, "page": page}

        response = requests.get(f"{url}/{val}", params=params)
        response.raise_for_status()
        data = response.json()

        results = data.get(val, [])
        if not results:
            if verbose:
                print("All pages fetched.")
            break

        all_areas.extend(results)
        page += 1

        time.sleep(0.2)

    if verbose:
        print(f"Uploading {len(all_areas)} protected areas to gs://{bucket}/{archive_filename}")

    upload_dataframe(
        bucket, pd.DataFrame(all_areas), archive_filename, project_id=project, verbose=True
    )
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet(
    wdpa_global_level_file_name=WDPA_GLOBAL_LEVEL_FILE_NAME,
    archive_wdpa_global_level_file_name=ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    wdpa_country_level_file_name=WDPA_COUNTRY_LEVEL_FILE_NAME,
    archive_wdpa_country_level_file_name=ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    pp_api_key=PP_API_KEY,
    project_id=PROJECT,
    wdpa_global_url=WDPA_GLOBAL_LEVEL_URL,
    wdpa_url=WDPA_URL,
    api_url=WDPA_API_URL,
    wdpa_file_name=WDPA_FILE_NAME,
    archive_wdpa_file_name=ARCHIVE_WDPA_FILE_NAME,
    bucket=BUCKET,
    verbose=True,
):
    # download wdpa
    download_and_duplicate_zipfile(
        wdpa_url, bucket, wdpa_file_name, archive_wdpa_file_name, chunk_size=8192, verbose=verbose
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
        val="countries",
        bucket=bucket,
        project=project_id,
        url=api_url,
        per_page=50,
        verbose=verbose,
    )


def download_habitats(
    habitats_url=HABITATS_URL,
    habitats_file_name=HABITATS_FILE_NAME,
    archive_habitats_file_name=ARCHIVE_HABITATS_FILE_NAME,
    seamounts_url=SEAMOUNTS_URL,
    seamounts_file_name=SEAMOUNTS_FILE_NAME,
    archive_seamounts_file_name=ARCHIVE_SEAMOUNTS_FILE_NAME,
    bucket=BUCKET,
    chunk_size=8192,
    verbose=True,
):
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


def main(request):
    data = request.get_json(silent=True) or {}
    method = data.get("METHOD", "default")

    if method == "dry_run":
        print("Dry Run Complete!")
    elif method == "download_eezs":
        # Run in CLI via:
        # gcloud functions call x30-dev-data --data '{"METHOD": "download_eezs"}' --region us-east1
        # TODO: add EEZ_params inputs to this and high seas
        download_eezs(blob_name=EEZ_ZIPFILE_NAME, verbose=verbose)
    elif method == "download_high_seas":
        # Run in CLI via:
        # gcloud functions call x30-dev-data --data '{"METHOD": "download_high_seas"}' \
        # --region us-east1
        download_high_seas(blob_name=HIGH_SEAS_ZIPFILE_NAME, verbose=verbose)
    elif method == "download_habitats":
        # Run in CLI via:
        # gcloud functions call x30-dev-data --data '{"METHOD": "download_habitats"}' \
        # --region us-east1
        download_habitats(
            habitats_url=HABITATS_URL,
            habitats_file_name=HABITATS_FILE_NAME,
            archive_habitats_file_name=ARCHIVE_HABITATS_FILE_NAME,
            seamounts_url=SEAMOUNTS_URL,
            seamounts_file_name=SEAMOUNTS_FILE_NAME,
            archive_seamounts_file_name=ARCHIVE_SEAMOUNTS_FILE_NAME,
            bucket=BUCKET,
            chunk_size=8192,
            verbose=True,
        )
    elif method == "download_mpatlas":
        download_mpatlas(
            url=MPATLAS_URL,
            bucket=BUCKET,
            filename=MPATLAS_FILE_NAME,
            archive_filename=ARCHIVE_MPATLAS_FILE_NAME,
            verbose=verbose,
        )
    elif method == "download_protected_seas":
        download_protected_seas(
            url=PROTECTED_SEAS_URL,
            bucket=BUCKET,
            filename=PROTECTED_SEAS_FILE_NAME,
            archive_filename=ARCHIVE_PROTECTED_SEAS_FILE_NAME,
            project=PROJECT,
            verbose=verbose,
        )
    elif method == "download_protected_planet_wdpa":
        download_protected_planet(
            wdpa_global_level_file_name=WDPA_GLOBAL_LEVEL_FILE_NAME,
            archive_wdpa_global_level_file_name=ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
            wdpa_country_level_file_name=WDPA_COUNTRY_LEVEL_FILE_NAME,
            archive_wdpa_country_level_file_name=ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
            pp_api_key=PP_API_KEY,
            project_id=PROJECT,
            wdpa_global_url=WDPA_GLOBAL_LEVEL_URL,
            wdpa_url=WDPA_URL,
            api_url=WDPA_API_URL,
            wdpa_file_name=WDPA_FILE_NAME,
            archive_wdpa_file_name=ARCHIVE_WDPA_FILE_NAME,
            bucket=BUCKET,
            verbose=True,
        )
    else:
        print(f"METHOD: {method} not a valid option")

    return "OK", 200
