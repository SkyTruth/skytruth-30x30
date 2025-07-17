import os

import functions_framework
from flask import Request

from src.methods import (
    download_habitats,
    download_mpatlas,
    download_protected_planet,
    download_protected_seas,
)
from src.params import (
    CHUNK_SIZE,
    EEZ_PARAMS,
    EEZ_ZIPFILE_NAME,
    GADM_URL,
    GADM_ZIPFILE_NAME,
    HIGH_SEAS_PARAMS,
    HIGH_SEAS_ZIPFILE_NAME,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    MARINE_REGIONS_URL,
)
from src.utils.gcp import download_zip_to_gcs

verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "BAD!")


@functions_framework.http
def main(request: Request) -> tuple[str, int]:
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
                download_habitats(verbose=verbose)

            case "download_mpatlas":
                download_mpatlas(verbose=verbose)

            case "download_protected_seas":
                download_protected_seas(verbose=verbose)

            case "download_protected_planet_wdpa":
                download_protected_planet(verbose=verbose)

            case "download_gadm":
                download_zip_to_gcs(
                    GADM_URL,
                    BUCKET,
                    GADM_ZIPFILE_NAME,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case _:
                print(f"METHOD: {method} not a valid option")

        print("Process complete!")

        return "OK", 200
    except Exception as e:
        print(f"METHOD {method} failed: {e}")

        return f"Internal Server Error: {e}", 500
