import gc
import os

import pandas as pd
import pyarrow

from src.core.commons import (
    add_tolerance_suffix,
    download_file_with_progress,
    remove_file_or_folder,
    retry_and_alert,
    unzip_file,
)
from src.core.params import (
    ARCHIVE_RAW_WDPA_FILE_NAME,
    BUCKET,
    PROJECT,
    TOLERANCE,
    WDPA_MARINE_FILE_NAME,
    WDPA_META_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
    WDPA_URL,
)
from src.core.processors import match_old_pa_naming_convantion
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry
from src.methods.download_and_process.wdpa_geometries import process_protected_area_geoms
from src.methods.download_and_process.wdpa_unpack import unpack_pas_to_parquet
from src.utils.gcp import (
    duplicate_blob,
    upload_dataframe,
    upload_file_to_gcs,
    upload_gdf,
)
from src.utils.logger import Logger
from src.utils.resource_handling import show_container_mem

logger = Logger()


def download_and_process_protected_planet_pas(
    wdpa_url: str = WDPA_URL,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    meta_file_name: str = WDPA_META_FILE_NAME,
    archive_wdpa_file_name: str = ARCHIVE_RAW_WDPA_FILE_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = True,
    bucket: str = BUCKET,
    project_id: str = PROJECT,
    batch_size=1000,
    n_jobs=-1,
):
    show_container_mem("Start")

    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    base_zip_path = os.path.join(tmp_dir, "wdpa.zip")
    pa_dir = os.path.join(tmp_dir, "wdpa")

    # download WDPA shapefiles and return CloudRun retry config
    # to try once per day for a week if fails
    if verbose:
        logger.info({"message": f"downloading {wdpa_url}"})
    # Do not send alert unless it fails all retries
    status = download_file_with_progress(wdpa_url, base_zip_path, verbose=verbose)
    if not status:
        cfg = METHOD_RETRY_CONFIGS["download_protected_planet_pas"]
        raise ScheduleRetry(
            delay_seconds=cfg["delay_seconds"],
            max_retries=cfg["max_retries"],
            message=f"Failed to download {wdpa_url}",
        )

    show_container_mem("After download")

    # Save to archive in GCS
    if verbose:
        logger.info({"message": f"Saving to archive at {archive_wdpa_file_name}"})
    upload_file_to_gcs(
        bucket=bucket,
        file_name=base_zip_path,
        blob_name=archive_wdpa_file_name,
    )

    if verbose:
        logger.info({"message": f"unzipping {base_zip_path}"})
    _ = unzip_file(base_zip_path, pa_dir)
    show_container_mem("After unzipping")

    if verbose:
        logger.info({"message": "unpacking PA shapefiles into parquet files"})
    unpack_pas_to_parquet(pa_dir, verbose=verbose)
    show_container_mem("After unpacking")

    if verbose:
        logger.info({"message": f"deleting {base_zip_path}"})
    remove_file_or_folder(base_zip_path, verbose=verbose)
    show_container_mem(f"After deleting {base_zip_path}")

    if verbose:
        logger.info({"message": "processing and simplifying protected area geometries"})

    try:
        if verbose:
            logger.info({"message": f"processing with tolerance {tolerance}"})
        df = process_protected_area_geoms(
            pa_dir, tolerance=tolerance, batch_size=batch_size, n_jobs=n_jobs, verbose=verbose
        )

        if verbose:
            logger.info({"message": "Renaming variables to match old format"})
        # On failure, alert in case naming convention has changed
        df = retry_and_alert(
            match_old_pa_naming_convantion,
            df,
            max_retries=0,
            alert_message="Failed to match WDPA format - possible change to data format",
        )

        if verbose:
            logger.info({"message": f"saving wdpa metadata to {meta_file_name}"})

        retry_and_alert(
            upload_dataframe,
            bucket,
            df.drop(columns="geometry"),
            meta_file_name,
            project_id=project_id,
            verbose=verbose,
            alert_message="Failed to save WDPA metadata",
        )

        # Save terrestrial PAs
        ter_out_fn = add_tolerance_suffix(terrestrial_pa_file_name, tolerance)
        if verbose:
            logger.info({"message": f"saving and duplicating terrestrial PAs to {ter_out_fn}"})

        retry_and_alert(
            upload_gdf,
            bucket,
            df[df["MARINE"].eq("0")],
            ter_out_fn,
            alert_message="Failed to upload terrestrial PAs",
        )
        duplicate_blob(bucket, ter_out_fn, f"archive/{ter_out_fn}", verbose=verbose)

        # Save marine PAs
        mar_out_fn = add_tolerance_suffix(marine_pa_file_name, tolerance)
        if verbose:
            logger.info({"message": f"saving and duplicating marine PAs to {mar_out_fn}"})

        retry_and_alert(
            upload_gdf,
            bucket,
            df[df["MARINE"].isin(["1", "2"])],
            mar_out_fn,
            alert_message="Failed to upload marine PAs",
        )
        duplicate_blob(bucket, mar_out_fn, f"archive/{mar_out_fn}", verbose=verbose)
    finally:
        df = pd.DataFrame()
        gc.collect()
        pyarrow.default_memory_pool().release_unused()
        show_container_mem(f"After tolerance {tolerance}")

    if verbose:
        logger.info({"message": f"deleting {pa_dir}"})
    remove_file_or_folder(pa_dir, verbose=verbose)
