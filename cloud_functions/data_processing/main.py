import base64
import datetime
import json
import os
import signal

import functions_framework
from flask import Request

from src.core import map_params
from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    CONSERVATION_BUILDER_MARINE_DATA,
    CONSERVATION_BUILDER_TERRESTRIAL_DATA,
    EEZ_FILE_NAME,
    EEZ_PARAMS,
    FISHING_PROTECTION_FILE_NAME,
    GADM_FILE_NAME,
    GADM_URL,
    GADM_ZIPFILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    HIGH_SEAS_PARAMS,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    MARINE_REGIONS_URL,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    TOLERANCES,
    WDPA_MARINE_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
    verbose,
)
from src.core.strapi import Strapi
from src.methods.database_uploads import (
    upload_locations,
    upload_protected_areas,
    upload_stats,
)
from src.methods.download_and_process import (
    download_and_process_protected_planet_pas,
    download_mpatlas,
    download_protected_planet,
    download_protected_seas,
)
from src.methods.generate_static_tables import generate_locations_table
from src.methods.generate_tables import (
    generate_fishing_protection_table,
    generate_habitat_protection_table,
    generate_marine_protection_level_stats_table,
    generate_protected_areas_diff_table,
    generate_protection_coverage_stats_table,
)
from src.methods.publisher import create_task, monthly_job_publisher, pipe_next_steps
from src.methods.static_processes import (
    download_marine_habitats,
    generate_terrestrial_biome_stats_country,
    process_eez_gadm_unions,
    process_eez_geoms,
    process_gadm_geoms,
    process_mangroves,
    process_terrestrial_biome_raster,
)
from src.methods.subtract_geometries import generate_total_area_minus_pa
from src.methods.terrestrial_habitats import generate_terrestrial_biome_stats_pa
from src.methods.tileset_processes import (
    create_and_update_country_tileset,
    create_and_update_eez_tileset,
    create_and_update_marine_regions_tileset,
    create_and_update_protected_area_tileset,
    create_and_update_terrestrial_regions_tileset,
)
from src.utils.gcp import download_zip_to_gcs
from src.utils.logger import Logger
from src.utils.resource_handling import handle_sigterm, release_memory

logger = Logger()


# Register SIGTERM handler
signal.signal(signal.SIGTERM, handle_sigterm)


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
    - "generate_protected_areas_diff_table": Updates protected areas table

    Parameters:
    ----------
    request : flask.Request
        The incoming HTTP request. Must include a JSON body with a 'METHOD' key.

    Returns:
    -------
    Tuple[str, int]
        A tuple of ("OK", 200) to signal successful completion to the client.
    """

    st = datetime.datetime.now()

    project = os.environ.get("PROJECT", "")
    env = os.environ.get("ENVIRONMENT", "")
    location = os.environ.get("LOCATION", "")

    try:
        data = request.get_json(silent=True) or {}

        # in case received as a queue message
        if "message" in data:
            msg = data["message"]
            data_bytes = base64.b64decode(msg["data"])
            data = json.loads(data_bytes.decode("utf-8"))

        method = data.get("METHOD", "dry_run")
        trigger_next = data.get("TRIGGER_NEXT", False)
        tolerance = data.get("TOLERANCE", TOLERANCES[0])
        max_retries = data.get("MAX_RETRIES", 0)
        attempt = data.get("attempt", 1)

        task_config = {
            "PROJECT": project,
            "LOCATION": location,
            "QUEUE_NAME": data.get("QUEUE_NAME", ""),
            "TARGET_URL": data.get("TARGET_URL", ""),
            "INVOKER_SA": data.get("INVOKER_SA", ""),
            "TRIGGER_NEXT": trigger_next,
            "MAX_RETRIES": max_retries,
            "attempt": attempt,
        }

        retry_config = {"delay_seconds": (attempt - 1) * 60, "max_retries": max_retries}

        print(f"Starting METHOD: {method}")

        match method:
            case "dry_run":
                print("Dry Run Complete!")

            case "test_retries":
                retry_config = {"delay_seconds": 30, "max_retries": 3}
                raise ValueError("Error: Testing Retries")
            case "publisher":
                monthly_job_publisher(task_config, verbose=verbose)

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
                step_list = ["process_gadm"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

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

                step_list = ["process_eezs", "process_eez_gadm_unions"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

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

                step_list = ["process_eezs", "process_eez_gadm_unions"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "process_gadm":
                process_gadm_geoms(verbose=verbose)

                step_list = ["generate_locations_table"]
                if env == "prod":
                    step_list = step_list + [
                        "update_country_tileset",
                        "update_terrestrial_regions_tileset",
                    ]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "process_eezs":
                process_eez_geoms(verbose=verbose)

                step_list = ["generate_locations_table"]

                if env == "prod":
                    step_list = step_list + ["update_eez_tileset", "update_marine_regions_tileset"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "process_eez_gadm_unions":
                process_eez_gadm_unions(verbose=verbose)

                step_list = ["process_mangroves"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "download_marine_habitats":
                download_marine_habitats(verbose=verbose)

            case "process_terrestrial_biomes":
                process_terrestrial_biome_raster(verbose=verbose)

                step_list = ["generate_terrestrial_biome_stats_country"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

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

                step_list = ["generate_marine_protection_level_stats_table"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "download_protected_seas":
                download_protected_seas(verbose=verbose)

                step_list = ["generate_fishing_protection_table"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "download_protected_planet_country":
                download_protected_planet(verbose=verbose)

                step_list = ["generate_protection_coverage_stats_table"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "download_protected_planet_pas":
                retry_config = download_and_process_protected_planet_pas(
                    verbose=verbose, tolerance=tolerance, batch_size=1000
                )
                if tolerance == TOLERANCES[0]:
                    step_list = [
                        "generate_protected_areas_table",
                        "generate_terrestrial_biome_stats",
                        "generate_gadm_minus_pa",
                        "generate_eez_minus_mpa",
                    ]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            # ------------------
            #   Table updates
            # ------------------

            case "generate_terrestrial_biome_stats":
                _ = generate_terrestrial_biome_stats_pa(verbose=verbose)

                step_list = ["generate_habitat_protection_table"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_habitat_protection_table":
                _ = generate_habitat_protection_table(verbose=verbose)

                step_list = ["update_habitat_protection_stats"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_protection_coverage_stats_table":
                _ = generate_protection_coverage_stats_table(verbose=verbose)

                step_list = ["update_protection_coverage_stats"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_marine_protection_level_stats_table":
                _ = generate_marine_protection_level_stats_table(verbose=verbose)

                step_list = ["update_mpaa_protection_level_stats"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_fishing_protection_table":
                _ = generate_fishing_protection_table(verbose=verbose)

                step_list = ["update_fishing_protection_stats"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_locations_table":
                generate_locations_table(verbose=verbose)

                step_list = ["update_locations"]
                pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_protected_areas_table":
                updates = generate_protected_areas_diff_table(verbose=verbose)

                if updates and env == "prod":
                    step_list = [
                        "update_protected_areas",
                        "update_marine_protected_areas_tileset",
                        "update_terrestrial_protected_areas_tileset",
                    ]
                    pipe_next_steps(step_list, trigger_next, task_config, verbose=verbose)

            case "generate_gadm_minus_pa":
                generate_total_area_minus_pa(
                    bucket=BUCKET,
                    total_area_file=GADM_FILE_NAME,
                    pa_file=WDPA_TERRESTRIAL_FILE_NAME,
                    out_file=CONSERVATION_BUILDER_TERRESTRIAL_DATA,
                    tolerance=map_params.WDPA_TOLERANCE,
                    verbose=verbose,
                )

            case "generate_eez_minus_mpa":
                generate_total_area_minus_pa(
                    bucket=BUCKET,
                    total_area_file=EEZ_FILE_NAME,
                    pa_file=WDPA_MARINE_FILE_NAME,
                    out_file=CONSERVATION_BUILDER_MARINE_DATA,
                    tolerance=map_params.WDPA_TOLERANCE,
                    verbose=verbose,
                )

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

            case "update_protected_areas":
                update_segment = data.get("UPDATE_SEGMENT", "all")
                upload_protected_areas(verbose=verbose, update_segment=update_segment)

            # ------------------
            #   Map Tilesets Updates
            # ------------------

            case "update_eez_tileset":
                create_and_update_eez_tileset(verbose=verbose)

            case "update_marine_regions_tileset":
                create_and_update_marine_regions_tileset(verbose=verbose)

            case "update_country_tileset":
                create_and_update_country_tileset(verbose=verbose)

            case "update_terrestrial_regions_tileset":
                create_and_update_terrestrial_regions_tileset(verbose=verbose)

            case "update_marine_protected_areas_tileset":
                create_and_update_protected_area_tileset(
                    bucket=BUCKET,
                    source_file=WDPA_MARINE_FILE_NAME,
                    tileset_file=map_params.MARINE_PA_TILESET_FILE,
                    tileset_id=map_params.MARINE_PA_TILESET_ID,
                    display_name=map_params.MARINE_PA_TILESET_NAME,
                    tolerance=map_params.WDPA_TOLERANCE,
                    verbose=verbose,
                )

            case "update_terrestrial_protected_areas_tileset":
                create_and_update_protected_area_tileset(
                    bucket=BUCKET,
                    source_file=WDPA_TERRESTRIAL_FILE_NAME,
                    tileset_file=map_params.TERRESTRIAL_PA_TILESET_FILE,
                    tileset_id=map_params.TERRESTRIAL_PA_TILESET_ID,
                    display_name=map_params.TERRESTRIAL_PA_TILESET_NAME,
                    tolerance=map_params.WDPA_TOLERANCE,
                    verbose=verbose,
                )

            case _:
                print(f"METHOD: {method} not a valid option")

        print(f"METHOD: {method} complete!")

        return "OK", 200
    except Exception as e:
        if retry_config and attempt <= retry_config["max_retries"]:
            logger.warning({"message": f"METHOD {method} failed attempt {attempt}: {e}"})
            payload = {"METHOD": method, "attempt": attempt + 1, **task_config}
            create_task(
                payload=payload, verbose=verbose, delay_seconds=retry_config["delay_seconds"]
            )
            return "retrying", 200
        else:
            logger.error({"message": f"METHOD {method} failed after {attempt} attempts: {e}"})
            return f"Internal Server Error - METHOD {method} failed: {e}", 500

    finally:
        print("Releasing memory")
        release_memory(verbose=verbose)

        fn = datetime.datetime.now()
        print(f"Completed in {(fn - st).total_seconds() / 60:.2f} minutes")
