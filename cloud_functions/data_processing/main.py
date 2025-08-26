import functions_framework
from flask import Request

from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    EEZ_PARAMS,
    FISHING_PROTECTION_FILE_NAME,
    GADM_URL,
    GADM_ZIPFILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    HIGH_SEAS_PARAMS,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    MARINE_REGIONS_URL,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    verbose,
)
from src.core.strapi import Strapi
from src.methods.database_uploads import (
    upload_locations,
    upload_stats,
)
from src.methods.download_and_process import (
    download_mpatlas,
    download_protected_planet,
    download_protected_seas,
    process_protected_area_geoms,
)
from src.methods.generate_static_tables import generate_locations_table
from src.methods.generate_tables import (
    generate_fishing_protection_table,
    generate_habitat_protection_table,
    generate_marine_protection_level_stats_table,
    generate_protected_areas_table,
    generate_protection_coverage_stats_table,
)
from src.methods.static_processes import (
    download_marine_habitats,
    generate_terrestrial_biome_stats_country,
    process_eez_gadm_unions,
    process_eez_geoms,
    process_gadm_geoms,
    process_mangroves,
    process_terrestrial_biome_raster,
)
from src.methods.terrestrial_habitats import generate_terrestrial_biome_stats_pa
from src.methods.tileset_processes import create_and_update_eez_tileset
from src.utils.gcp import download_zip_to_gcs


@functions_framework.http
def main(request: Request) -> tuple[str, int]:
    """
    Cloud Function entry point that dispatches behavior based on the 'METHOD' key
    in the incoming HTTP request body. Each METHOD corresponds to a specific data
    download task, often writing to Google Cloud Storage.

    The function expects a JSON body with a `METHOD` key. Supported METHOD values include:

    - "dry_run": Simple test mode, prints confirmation only

    Static (infrequent updates, done manually)
    - "download_gadm": Downloads GADM country shapefiles from UC Davis
    - "download_eezs": Downloads EEZ shapefiles from Marine Regions API
    - "download_eez_land_union": Downloads EEZ/land union shapefiles from Marine Regions API
    - "download_high_seas": Downloads high seas shapefiles from Marine Regions API
    - "download_habitats": Downloads and stores habitat and seamount shapefiles
    - "process_terrestrial_biomes": Processes biome raster --> done once after raster download
    - "process_mangroves": Process mangroves --> done only after new mangroves data download or
            updated eez/land union raster
    - "generate_terrestrial_biome_stats_country": Calculates area of each biome in country
            --> only run after gadm or biome raster is updated

    Regularly Updated (automated)
    - "download_mpatlas": Downloads MPAtlas dataset and stores current + archive versions
    - "download_protected_seas": Downloads Protected Seas JSON data and uploads it
    - "download_protected_planet_wdpa": Downloads full Protected Planet suite
            (WDPA ZIP + stats) and processes/simplifies polygons
    - "generate_protected_areas_table": Updates protected areas table

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
            # ------------------------------------------------------
            #                    Nearly Static
            # ------------------------------------------------------
            case "download_gadm":
                download_zip_to_gcs(
                    url=GADM_URL,
                    bucket_name=BUCKET,
                    blob_name=GADM_ZIPFILE_NAME,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "process_gadm":
                # NOTE: download_gadm must have been run first
                process_gadm_geoms(verbose=verbose)

            case "download_eezs":
                download_zip_to_gcs(
                    url=MARINE_REGIONS_URL,
                    bucket_name=BUCKET,
                    blob_name=EEZ_PARAMS["zipfile_name"],
                    data=MARINE_REGIONS_BODY,
                    params=EEZ_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "download_high_seas":
                download_zip_to_gcs(
                    url=MARINE_REGIONS_URL,
                    bucket_name=BUCKET,
                    blob_name=HIGH_SEAS_PARAMS["zipfile_name"],
                    data=MARINE_REGIONS_BODY,
                    params=HIGH_SEAS_PARAMS,
                    headers=MARINE_REGIONS_HEADERS,
                    chunk_size=CHUNK_SIZE,
                    verbose=verbose,
                )

            case "process_eezs":
                # NOTE: download_eezs and download_high_seas must have been run first
                process_eez_geoms(verbose=verbose)

            case "process_eez_gadm_unions":
                # NOTE: Must be run after download_gadm,
                # process_gadm, download_high_seas, download_eezs, and process_eezs
                process_eez_gadm_unions(verbose=verbose)

            case "download_marine_habitats":
                download_marine_habitats(verbose=verbose)

            case "process_terrestrial_biomes":
                process_terrestrial_biome_raster(verbose=verbose)

            case "process_mangroves":
                process_mangroves(verbose=verbose)

            case "generate_terrestrial_biome_stats_country":
                generate_terrestrial_biome_stats_country(verbose=verbose)

            # ------------------------------------------------------
            #                    Update monthly
            # ------------------------------------------------------

            # ------------------
            #     Downloads
            # ------------------
            case "download_mpatlas":
                download_mpatlas(verbose=verbose)

            case "download_protected_seas":
                download_protected_seas(verbose=verbose)

            case "download_protected_planet_wdpa":
                download_protected_planet(verbose=verbose)
                _ = process_protected_area_geoms(verbose=verbose)

            # ------------------
            #   Table updates
            # ------------------
            case "generate_protected_areas_table":
                # TODO: incomplete!
                _ = generate_protected_areas_table(verbose=verbose)

            case "generate_habitat_protection_table":
                _ = generate_terrestrial_biome_stats_pa(verbose=verbose)
                _ = generate_habitat_protection_table(verbose=verbose)

            case "generate_protection_coverage_stats_table":
                _ = generate_protection_coverage_stats_table(verbose=verbose)

            case "generate_marine_protection_level_stats_table":
                _ = generate_marine_protection_level_stats_table(verbose=verbose)

            case "generate_fishing_protection_table":
                _ = generate_fishing_protection_table(verbose=verbose)

            case "generate_locations_table":
                generate_locations_table(verbose=verbose)

            # ------------------
            #   Database updates
            # ------------------

            case "update_locations":
                return upload_locations(request=data, verbose=verbose)

            case "update_protection_coverage_stats":
                client = Strapi()
                return upload_stats(
                    filename=PROTECTION_COVERAGE_FILE_NAME,
                    upload_function=client.upsert_protection_coverage_stats,
                    verbose=verbose,
                )

            case "update_mpaa_protection_level_stats":
                client = Strapi()
                return upload_stats(
                    filename=PROTECTION_LEVEL_FILE_NAME,
                    upload_function=client.upsert_mpaa_protection_level_stats,
                    verbose=verbose,
                )

            case "update_fishing_protection_stats":
                client = Strapi()
                return upload_stats(
                    filename=FISHING_PROTECTION_FILE_NAME,
                    upload_function=client.upsert_fishing_protection_level_stats,
                    verbose=verbose,
                )

            case "update_habitat_protection_stats":
                client = Strapi()
                return upload_stats(
                    filename=HABITAT_PROTECTION_FILE_NAME,
                    upload_function=client.upsert_habitat_stats,
                    verbose=verbose,
                )
            
            # ------------------
            #   Map Tilesets Updates
            # ------------------
            
            case "update_eez_tileset":
                create_and_update_eez_tileset()

            case _:
                print(f"METHOD: {method} not a valid option")

        print("Process complete!")

        return "OK", 200
    except Exception as e:
        print(f"METHOD {method} failed: {e}")

        return f"Internal Server Error: {e}", 500
