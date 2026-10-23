from ast import literal_eval

import pandas as pd
from tqdm import tqdm

from src.core.commons import retry_and_alert
from src.core.params import (
    ARCHIVE_WDPA_PA_FILE_NAME,
    BUCKET,
    LOCATIONS_FILE_NAME,
    PROJECT,
    WDPA_PA_FILE_NAME,
)
from src.core.strapi import Strapi
from src.utils.gcp import load_pickle_from_gcs, read_dataframe, rename_blob
from src.utils.logger import Logger

logger = Logger()


def upload_locations(
    bucket: str = BUCKET,
    filename: str = LOCATIONS_FILE_NAME,
    request: dict = None,
    verbose: bool = True,
):
    """
    Prepares processed locations csv and passes it to Strapi method to update the database
    with data included in the csv.

    Preparation inlcudes:
    - converting stringified lists to actual lists
    - removing empty values
    - converting to a dict
    """
    list_fields = ["groups", "members", "terrestrial_bounds", "marine_bounds"]
    target_fields = [
        "marine_target",
        "marine_target_year",
        "terrestrial_target",
        "terrestrial_target_year",
    ]
    integer_fields = ["total_marine_area", "total_terrestrial_area", *target_fields]
    unsupported_fields = [
        "terrestrial_target",
        "terrestrial_target_year",
        "ort_record",
    ]

    converters = {field: _parse_list_or_na for field in list_fields}
    locs_df = read_dataframe(bucket_name=bucket, filename=filename, converters=converters)

    # Strapi stores these as integers while some targets are published as fractions. Empty cells,
    # such as the marine area of a land locked country, read back as "" rather than NA, which
    # _extract_non_na_values would otherwise keep.
    locs_df[integer_fields] = (
        locs_df[integer_fields].apply(pd.to_numeric, errors="coerce").round().astype("Int64")
    )

    # Every column is upserted, so drop the ones the Strapi location schema does not define yet
    locs_df = locs_df.drop(columns=unsupported_fields)

    # Remove keys with NA values, this will allow us ot only upsert data we actually have
    # rather than stubbing defaults. Targets are the exception: the pipeline resolves them for
    # every location, so an empty one is sent as null to clear a target that has been withdrawn.
    locations = _extract_non_na_values(locs_df, null_fields=target_fields)

    options = request.get("options") if request else None

    if verbose:
        logger.info({"message": "Writing locations to the database"})

    client = Strapi()
    return client.upsert_locations(locations, options)


def _extract_non_na_values(df: pd.DataFrame, null_fields: list[str] | None = None) -> list[dict]:
    """
    Converts a dataframe to a dictionary while leaving off any None/NA/NaN values.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to convert, one dictionary per row.
    null_fields : list[str], optional
        Fields sent as null when empty instead of being left off, so that a value the pipeline
        owns can be cleared rather than kept by Strapi's partial update. pd.NA is not JSON
        serializable, so these are converted to None.
    """
    null_fields = set(null_fields or [])

    cleaned = []
    for row in df.to_dict(orient="records"):
        kept = {}
        for key, val in row.items():
            if isinstance(val, list) or pd.notna(val):
                kept[key] = val
            elif key in null_fields:
                kept[key] = None
        cleaned.append(kept)

    return cleaned


def _parse_list_or_na(val):
    """
    Helper method to parse lists for a dict when read from csv. Lists in csvs become
    stringified, this takes a cell value and returns either a python list if the cell is a
    stringified list, otherwise it will for the value into a list unless the value is NA or "" -
    typically this represents an empty cell in a csv - then it will return pd.NA
    """
    if pd.isna(val) or val == "":
        return pd.NA
    try:
        parsed_val = literal_eval(val)
        return parsed_val if isinstance(parsed_val, list) else [parsed_val]
    except (ValueError, SyntaxError):
        return pd.NA  # fallback if bad format


def upload_stats(
    filename: str,
    upload_function: callable,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """
    Pass through function for writing generated CSV tables to the database via the API.
    Reads the CSV stored in a GCS bucket at bucket/filename, converts it to a dictionary and
    uplaods to the DB via the API by way of a passed in upload_function
    """
    stats_df = read_dataframe(bucket_name=bucket, filename=filename)
    stats_dict = stats_df.to_dict(orient="records")

    if verbose:
        logger.info({"message": f"Uploading stats from {filename} via the API"})
    return upload_function(stats_dict)


def upload_protected_areas(
    pa_file_name: str = WDPA_PA_FILE_NAME,
    archive_pa_file_name: str = ARCHIVE_WDPA_PA_FILE_NAME,
    bucket: str = BUCKET,
    update_segment: str = "all",
    verbose: bool = True,
):
    strapi = Strapi()

    # To prevent this from updating based on a stale change file name, load
    # change file and then archive the file. This way, if it unexpectedly runs again,
    # the expected (non-archived) file does not exist and it will fail to execute.
    db_changes = retry_and_alert(
        load_pickle_from_gcs,
        bucket_name=bucket,
        blob_name=pa_file_name,
        project_id=PROJECT,
        verbose=verbose,
        max_retries=0,
        alert_message=f"failed to load {pa_file_name}",
    )
    rename_blob(bucket, pa_file_name, archive_pa_file_name, verbose=True)

    if update_segment in ["delete", "all"]:
        deleted = db_changes["deleted"]
        if verbose:
            logger.info({"message": f"deleting {len(deleted)} entries"})
        delete_response = strapi.delete_pas(deleted)
        if verbose:
            logger.info({"message": f"delete response: {delete_response}"})

    if update_segment in ["upsert", "all"]:
        upserted = db_changes["new"] + db_changes["changed"]
        if verbose:
            logger.info({"message": f"upserting {len(upserted)} entries"})

        wdpaids = sorted(set([u["wdpaid"] for u in upserted]))
        chunk_size = 10000
        total_chunks = (len(wdpaids) + chunk_size - 1) // chunk_size
        for chunk_idx, i in enumerate(
            tqdm(range(0, len(wdpaids), chunk_size), desc="Upserting to Strapi"),
            start=1,
        ):
            ids = wdpaids[i : i + chunk_size]
            chunk = [u for u in upserted if u["wdpaid"] in ids]
            try:
                logger.info({"message": f"upserting chunk {chunk_idx} of {total_chunks}"})
                upsert_response = strapi.upsert_pas(chunk)

                if verbose:
                    logger.info({"message": f"upsert response: {upsert_response}"})
            except Exception as excep:
                logger.error({"message": f"Error on chunk {chunk_idx} of {total_chunks}"})
                raise excep

    if verbose:
        logger.info({"message": "Update complete!"})
