import os
import sys
import functions_framework
from flask import Request

from src.params import (
    CHUNK_SIZE,
    GADM_URL,
    GADM_ZIPFILE_NAME,
    MARINE_REGIONS_URL,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    EEZ_PARAMS,
    HIGH_SEAS_PARAMS,
    EEZ_LAND_UNION_PARAMS,
)
from src.utils.gcp import download_zip_to_gcs


from src.methods import (
    download_habitats,
    download_mpatlas,
    download_protected_planet,
    download_protected_seas,
    generate_fishing_protection_table,
    generate_habitat_protection_table,
    generate_marine_protection_level_stats_table,
    generate_protected_areas_table,
    generate_protection_coverage_stats_table,
    preprocess_mangroves,
)

sys.path.append("./src")

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

            case "download_gadm":
                download_zip_to_gcs(
                    GADM_URL,
                    BUCKET,
                    GADM_ZIPFILE_NAME,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_eezs":
                download_zip_to_gcs(
                    MARINE_REGIONS_URL,
                    BUCKET,
                    EEZ_PARAMS["zipfile_name"],
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
                    HIGH_SEAS_PARAMS["zipfile_name"],
                    data=MARINE_REGIONS_BODY,
                    params=HIGH_SEAS_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_eez_land_union":
                download_zip_to_gcs(
                    MARINE_REGIONS_URL,
                    BUCKET,
                    EEZ_LAND_UNION_PARAMS["zipfile_name"],
                    data=MARINE_REGIONS_BODY,
                    params=EEZ_LAND_UNION_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=True,
                )

            case "download_habitats":
                download_habitats(verbose=verbose)

            case "download_mpatlas":
                download_mpatlas(verbose=verbose)

            case "download_protected_seas":
                download_protected_seas(verbose=verbose)

            case "download_protected_planet_wdpa":
                download_protected_planet(verbose=verbose)

            case "generate_protected_areas_table":
                generate_protected_areas_table(verbose=verbose)

            case "generate_habitat_protection_table":
                generate_habitat_protection_table(verbose=verbose)

            case "generate_protection_coverage_stats_table":
                generate_protection_coverage_stats_table(verbose=verbose)

            case "generate_marine_protection_level_stats_table":
                generate_marine_protection_level_stats_table(verbose=verbose)

            case "generate_fishing_protection_table":
                generate_fishing_protection_table(verbose=verbose)

            case _:
                print(f"METHOD: {method} not a valid option")

        # TODO: should this be a triggered cloudrun or is this ok? Also
        # there is no download_mangroves yet, may add eventually
        if method in ["download_eez_land_union", "download_mangroves"]:
            preprocess_mangroves()

        print("Process complete!")

        return "OK", 200
    except Exception as e:
        print(f"METHOD {method} failed: {e}")

        return f"Internal Server Error: {e}", 500
