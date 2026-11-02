import json

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

from src.core.commons import RetryFailed, retry_and_alert
from src.core.params import (
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    ARCHIVE_MPATLAS_GLOBAL_FILE_NAME,
    BUCKET,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_GLOBAL_API_URL,
    MPATLAS_GLOBAL_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    MPATLAS_URL,
    PROJECT,
)
from src.core.processors import calculate_area
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry
from src.utils.gcp import (
    duplicate_blob,
    read_json_from_gcs,
    save_file_bucket,
    upload_dataframe,
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


def download_mpatlas_global(
    bucket: str = BUCKET,
    url: str = MPATLAS_GLOBAL_API_URL,
    current_filename: str = MPATLAS_GLOBAL_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_GLOBAL_FILE_NAME,
    verbose: bool = True,
):
    response = requests.get(url)
    response.raise_for_status()

    if verbose:
        logger.info(
            {"message": f"saving MPAtlas Global API Data to gs://{bucket}/{current_filename}"}
        )
    save_file_bucket(
        response.content,
        response.headers.get("Content-Type"),
        current_filename,
        bucket,
        verbose=verbose,
    )

    duplicate_blob(bucket, current_filename, archive_filename, verbose=True)


# MPAtlas API v4 property names -> internal (v2-era) names used by the pipeline
MPATLAS_V4_FIELD_MAP = {
    "zone_name": "name",
    "site_designation": "designation",
    "mpaguide_protection_level": "protection_mpaguide_level",
    "assessment_establishment_stage": "establishment_stage",
}


def normalize_mpatlas_geojson(data: dict) -> dict:
    """
    Rename MPAtlas API v4 feature properties in place to the internal names
    used throughout the pipeline.

    v4's establishment_stage is site-level; the zone-effective value moved to
    assessment_establishment_stage, which replaces it here. Properties absent
    from a feature are left alone, so already-normalized data passes through
    unchanged.
    """
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        if "assessment_establishment_stage" in properties:
            properties.pop("establishment_stage", None)
        for v4_name, internal_name in MPATLAS_V4_FIELD_MAP.items():
            if v4_name in properties:
                properties[internal_name] = properties.pop(v4_name)
    return data


def download_mpatlas_zone(
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
        logger.info({"message": f"downloading MPAtlas Zone Assessment from {url}"})

    response = requests.get(url)
    response.raise_for_status()

    if verbose:
        logger.info(
            {"message": f"saving MPAtlas Zone Assessment to gs://{bucket}/{archive_filename}"}
        )
    save_file_bucket(
        response.content,
        response.headers.get("Content-Type"),
        archive_filename,
        bucket,
        verbose=verbose,
    )

    # The archive keeps the raw v4 response; the working copy is normalized to
    # the internal field names so downstream readers stay unchanged.
    if verbose:
        logger.info({"message": f"saving normalized MPAtlas Zone Assessment to {filename}"})
    normalized = normalize_mpatlas_geojson(response.json())
    save_file_bucket(
        json.dumps(normalized).encode("utf-8"),
        "application/json",
        filename,
        bucket,
        verbose=verbose,
    )


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
    mpatlas_global_url: str = MPATLAS_GLOBAL_API_URL,
    mpatlas_global_file_name: str = MPATLAS_GLOBAL_FILE_NAME,
    archive_mpatlas_global_file_name: str = ARCHIVE_MPATLAS_GLOBAL_FILE_NAME,
    verbose: bool = True,
    project_id: str = PROJECT,
) -> None:
    def safe_shape(geom):
        try:
            return shape(geom) if geom else None
        except Exception:
            return None

    try:
        retry_and_alert(
            download_mpatlas_country,
            bucket=bucket,
            project=project,
            url=mpatlas_country_url,
            current_filename=mpatlas_country_file_name,
            archive_filename=archive_mpatlas_country_file_name,
            alert_message="failed to download MPAtlas country stats",
        )

        retry_and_alert(
            download_mpatlas_global,
            bucket=bucket,
            url=mpatlas_global_url,
            current_filename=mpatlas_global_file_name,
            archive_filename=archive_mpatlas_global_file_name,
            alert_message="failed to download MPAtlas global stats",
        )

        retry_and_alert(
            download_mpatlas_zone,
            url=url,
            bucket=bucket,
            filename=mpatlas_filename,
            archive_filename=archive_mpatlas_filename,
            verbose=verbose,
            alert_message="failed to download MPAtlas zone stats",
        )

    except RetryFailed as e:
        cfg = METHOD_RETRY_CONFIGS["download_mpatlas"]
        raise ScheduleRetry(
            delay_seconds=cfg["delay_seconds"],
            max_retries=cfg["max_retries"],
            message=f"MPAtlas download failed: {e}",
        ) from e

    if verbose:
        logger.info({"message": f"loading MPAtlas from {mpatlas_filename}"})
    mpa = read_json_from_gcs(bucket, mpatlas_filename)

    mpa = gpd.GeoDataFrame(
        [
            {**feat["properties"], "geometry": safe_shape(feat.get("geometry"))}
            for feat in mpa["features"]
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    # add area column
    if verbose:
        logger.info({"message": "calculating MPA area (calculated_area_km2)"})
    mpa = calculate_area(mpa, output_area_column="calculated_area_km2")

    # add bounding box column
    if verbose:
        logger.info({"message": "calculating MPA bounding box (bbox)"})
    mpa["bbox"] = mpa.geometry.apply(lambda g: g.bounds if g is not None else None)

    # Upload metadata (no geometry)
    if verbose:
        logger.info({"message": f"saving metadata to {meta_file_name}"})
    upload_dataframe(
        bucket,
        mpa.drop(columns="geometry"),
        meta_file_name,
        project_id=project_id,
        verbose=verbose,
    )
