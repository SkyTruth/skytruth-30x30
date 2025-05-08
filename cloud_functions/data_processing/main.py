from io import BytesIO
import os
import pandas as pd
import requests
import time

from params import (
    MARINE_REGIONS_url,
    MARINE_REGIONS_body,
    MARINE_REGIONS_headers,
    EEZ_ZIPFILE_NAME,
    EEZ_params,
    HIGH_SEAS_ZIPFILE_NAME,
    HIGH_SEAS_params,
    MPATLAS_URL,
    MPATLAS_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    WDPA_API_URL,
    WDPA_FILE_NAME,
    ARCHIVE_WDPA_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
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


def download_eezs(blob_name=EEZ_ZIPFILE_NAME, verbose=True):
    """
    Downloads eez polygon zipfile from Marine Regions
    """
    download_zip_to_gcs(
        MARINE_REGIONS_url,
        BUCKET,
        blob_name,
        data=MARINE_REGIONS_body,
        params=EEZ_params,
        headers=MARINE_REGIONS_headers,
        chunk_size=8192,
        verbose=verbose,
    )


def download_high_seas(blob_name=HIGH_SEAS_ZIPFILE_NAME, verbose=True):
    """
    Downloads High Seas polygon zipfile from Marine Regions
    """
    download_zip_to_gcs(
        MARINE_REGIONS_url,
        BUCKET,
        blob_name,
        data=MARINE_REGIONS_body,
        params=HIGH_SEAS_params,
        headers=MARINE_REGIONS_headers,
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


def download_protected_planet_wdpa(
    blob_name=WDPA_FILE_NAME,
    archive_blob_name=ARCHIVE_WDPA_FILE_NAME,
    bucket=BUCKET,
    chunk_size=8192,
    verbose=True,
):
    """
    Download WDPA polygons from Protected Planet API and saves zipfile to a current
    file for calculations as well as an archive file
    """
    filename = archive_blob_name.split("/")[-1]
    url = f"https://d1gam3xoknrgr2.cloudfront.net/current/{filename}"

    if verbose:
        print(f"downloading {url} to gs://{bucket}/{archive_blob_name}")
    download_zip_to_gcs(url, bucket, archive_blob_name, chunk_size=chunk_size, verbose=verbose)
    duplicate_blob(bucket, archive_blob_name, blob_name, verbose=True)


def download_protected_planet_global(
    current_filename, archive_filename, project_id=PROJECT, url=WDPA_GLOBAL_LEVEL_URL, bucket=BUCKET
):
    response = requests.get(url)
    response.raise_for_status()
    data = pd.read_csv(BytesIO(response.content))

    upload_dataframe(bucket, data, current_filename, project_id=project_id, verbose=True)
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


def download_protected_planet_aggregates(
    protected_planet_global_filename,
    protected_planet_global_archive_filename,
    protected_planet_country_filename,
    protected_planet_country_archive_filename,
    pp_api_key=PP_API_KEY,
    project_id=PROJECT,
    url=WDPA_GLOBAL_LEVEL_URL,
    api_url=WDPA_API_URL,
    bucket=BUCKET,
    per_page=50,
    verbose=True,
):
    download_protected_planet_global(
        protected_planet_global_filename,
        protected_planet_global_archive_filename,
        project_id=project_id,
        url=url,
        bucket=bucket,
    )
    download_protected_planet_country(
        protected_planet_country_filename,
        protected_planet_country_archive_filename,
        pp_api_key,
        val="countries",
        bucket=bucket,
        project=project_id,
        url=api_url,
        per_page=per_page,
        verbose=verbose,
    )


def calculate_global_stats():
    return


def calculate_country_stats():
    return


def calculate_habitat_stats():
    return


def calculate_insights_table():
    return


def main(request):
    data = request.get_json(silent=True) or {}
    method = data.get("METHOD", "default")

    if method == "dry_run":
        print("Dry Run Complete!")
    elif method == "download_eezs":
        # TODO: currently no infra for this because they are essentially static
        # May keep this as a manual process
        download_eezs(blob_name=EEZ_ZIPFILE_NAME, verbose=verbose)
    elif method == "download_high_seas":
        # TODO: currently no infra for this because they are essentially static
        # May keep this as a manual process
        download_high_seas(blob_name=HIGH_SEAS_ZIPFILE_NAME, verbose=verbose)
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
        download_protected_planet_wdpa(
            blob_name=WDPA_FILE_NAME,
            archive_blob_name=ARCHIVE_WDPA_FILE_NAME,
            bucket=BUCKET,
            chunk_size=8192,
            verbose=verbose,
        )
    elif method == "download_protected_planet_aggregates":
        download_protected_planet_aggregates(
            WDPA_GLOBAL_LEVEL_FILE_NAME,
            ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
            WDPA_COUNTRY_LEVEL_FILE_NAME,
            ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
            pp_api_key=PP_API_KEY,
            project_id=PROJECT,
            url=WDPA_GLOBAL_LEVEL_URL,
            api_url=WDPA_API_URL,
            bucket=BUCKET,
            per_page=50,
            verbose=True,
        )
    elif method == "calculate_global_stats":
        calculate_global_stats()
    elif method == "calculate_country_stats":
        calculate_country_stats()
    elif method == "calculate_habitat_stats":
        calculate_habitat_stats()
    elif method == "calculate_insights_table":
        calculate_insights_table()
    else:
        print(f"METHOD: {method} not a valid option")

    return "OK", 200
