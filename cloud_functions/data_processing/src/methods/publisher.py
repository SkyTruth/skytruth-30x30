import json
import os
import traceback
from datetime import UTC, datetime, timedelta

from google.api_core import exceptions as gax_exceptions
from google.cloud import run_v2, tasks_v2
from google.protobuf import timestamp_pb2

from src.core import map_params
from src.core.commons import send_slack_alert
from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    CONSERVATION_BUILDER_MARINE_DATA,
    CONSERVATION_BUILDER_TERRESTRIAL_DATA,
    DISSOLVED_TERRESTRIAL_PA,
    EEZ_FILE_NAME,
    EEZ_PARAMS,
    FISHING_PROTECTION_FILE_NAME,
    GADM_FILE_NAME,
    GADM_URL,
    GADM_ZIPFILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    HIGH_SEAS_PARAMS,
    LONG_RUNNING_TASKS,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    MARINE_REGIONS_URL,
    PROTECTION_COVERAGE_FILE_NAME,
    PROTECTION_LEVEL_FILE_NAME,
    TOLERANCES,
    WDPA_MARINE_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
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
from src.methods.static_processes import (
    download_marine_habitats,
    generate_terrestrial_biome_stats_country,
    process_eez_gadm_unions,
    process_eez_geoms,
    process_gadm_geoms,
    process_mangroves,
    process_terrestrial_biome_raster,
)
from src.methods.subtract_geometries import dissolve_geometries, generate_total_area_minus_pa
from src.methods.terrestrial_habitats import generate_terrestrial_biome_stats_pa
from src.methods.tileset_processes import (
    create_and_update_country_tileset,
    create_and_update_eez_tileset,
    create_and_update_marine_regions_tileset,
    create_and_update_protected_area_tileset,
    create_and_update_terrestrial_regions_tileset,
)
from src.utils.database import update_cb
from src.utils.gcp import download_zip_to_gcs
from src.utils.logger import Logger
from src.utils.resource_handling import release_memory

logger = Logger()


def long_running_tasks(payload, timeout=5, verbose=True):
    if verbose:
        method = payload.get("METHOD", "")
        logger.info(
            {"message": f"Launching Long-Running Cloudfunction: {method}: {json.dumps(payload)}"}
        )

    client = run_v2.JobsClient()

    project_id = payload.get("PROJECT")
    location = payload.get("LOCATION")
    job_name = payload.get("JOB_NAME")

    run_payload = json.dumps(payload)
    job_resource_name = f"projects/{project_id}/locations/{location}/jobs/{job_name}"

    request = run_v2.RunJobRequest(
        name=job_resource_name,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(name="RUN_PAYLOAD", value=run_payload),
                    ]
                )
            ]
        ),
    )

    try:
        # Start the job execution
        operation = client.run_job(request=request, timeout=timeout)

        op_name = getattr(operation, "operation", None)
        op_name = getattr(op_name, "name", None) if op_name else None
        logger.info(
            {
                "message": "Cloud Run Job execution started",
                "job": job_resource_name,
                "operation": op_name,
            }
        )

    except gax_exceptions.DeadlineExceeded:
        # Don't wait for completion, and don't error if timeout
        pass
    except Exception as e:
        logger.error(
            {"message": "Error triggering Cloud Run Job", "error": str(e), "job": job_resource_name}
        )

    return "OK", 200


def create_task(
    payload,
    delay_seconds: int | None = None,
    verbose: bool = True,
):
    """Create a single Cloud Task to POST JSON to a Cloud Function."""

    project_id = payload.get("PROJECT", "")
    location = payload.get("LOCATION", "")
    queue = payload.get("QUEUE_NAME", "")
    target_url = payload.get("TARGET_URL", "")
    service_account_email = payload.get("INVOKER_SA", "")

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": target_url,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode(),
            "oidc_token": {"service_account_email": service_account_email},
        },
    }

    if delay_seconds is not None:
        scheduled_time = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(scheduled_time)
        task["schedule_time"] = timestamp

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project_id, location, queue)
        response = client.create_task(request={"parent": parent, "task": task})
        if verbose:
            logger.info({"message": f"Created task: {response.name}: {json.dumps(payload)}"})
        return response
    except Exception as e:
        logger.error({"message": f"Error creating Cloud Task: {e}"})
        raise


def monthly_job_publisher(task_config, long_running_task_list=None, verbose=True):
    """Enqueue the monthly tasks into Cloud Tasks."""

    jobs = [
        {
            "METHOD": "download_mpatlas",
            **task_config,
        },
        {
            "METHOD": "download_protected_seas",
            **task_config,
        },
        {
            "METHOD": "download_protected_planet_country",
            **task_config,
        },
    ]

    for tolerance in TOLERANCES:
        jobs.append(
            {
                "METHOD": "download_protected_planet_pas",
                **task_config,
                "TOLERANCE": tolerance,
            }
        )

    for job in jobs:
        if long_running_task_list and job["METHOD"] in long_running_task_list:
            long_running_tasks(job, verbose=verbose)
        else:
            create_task(job, verbose=verbose)


def launch_next_step(
    next_method: str,
    task_config: dict,
    task_type: str = "queue",
    verbose: bool = True,
):
    """Enqueue exactly one downstream task."""

    payload = {"METHOD": next_method, **task_config}

    if verbose:
        logger.info({"message": f"Launching next step with {task_type}: {next_method}"})

    if task_type == "queue":
        create_task(payload, verbose=verbose)
    elif task_type == "long_running_task":
        long_running_tasks(payload, verbose=verbose)


def pipe_next_steps(
    step_list: list,
    task_config: dict,
    long_running_task_list: list = None,
    verbose: bool = True,
):
    """Enqueue a sequence of downstream steps."""

    for next_method in step_list:
        if long_running_task_list and next_method in long_running_task_list:
            launch_next_step(
                next_method,
                task_config,
                task_type="long_running_task",
                verbose=verbose,
            )
        else:
            launch_next_step(
                next_method,
                task_config,
                task_type="queue",
                verbose=verbose,
            )


def dispatch_publisher(
    method,
    task_config,
    data,
    retry_config,
    trigger_next=False,
    env="staging",
    tolerance=TOLERANCES[0],
    verbose=True,
):
    # By default, do not continue onto the next step
    step_list = None

    # By default, continue to next steps - default to True, but will be reset to False if
    # method fails and retries are being handled with a scheduled task
    cont = True

    match method:
        case "dry_run":
            logger.info({"message": "Dry Run Complete!"})

        case "test_long_running_tasks":
            logger.info({"message": "Long Tasks Dry Run Complete!"})

        case "publisher":
            monthly_job_publisher(
                task_config, long_running_task_list=LONG_RUNNING_TASKS, verbose=verbose
            )

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

        case "process_gadm":
            process_gadm_geoms(verbose=verbose)
            step_list = ["generate_locations_table"]
            if env == "production":
                step_list = step_list + [
                    "update_country_tileset",
                    "update_terrestrial_regions_tileset",
                ]

        case "process_eezs":
            process_eez_geoms(verbose=verbose)
            step_list = ["generate_locations_table"]
            if env == "production":
                step_list = step_list + ["update_eez_tileset", "update_marine_regions_tileset"]

        case "process_eez_gadm_unions":
            process_eez_gadm_unions(verbose=verbose)
            step_list = ["process_mangroves"]

        case "download_marine_habitats":
            download_marine_habitats(verbose=verbose)

        case "process_terrestrial_biomes":
            process_terrestrial_biome_raster(verbose=verbose)
            step_list = ["generate_terrestrial_biome_stats_country"]

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
            retry_config, cont = download_mpatlas(verbose=verbose)
            step_list = ["generate_marine_protection_level_stats_table"]

        case "download_protected_seas":
            download_protected_seas(verbose=verbose)
            step_list = ["generate_fishing_protection_table"]

        case "download_protected_planet_country":
            download_protected_planet(verbose=verbose)
            step_list = ["generate_protection_coverage_stats_table"]

        case "download_protected_planet_pas":
            retry_config, cont = download_and_process_protected_planet_pas(
                verbose=verbose,
                tolerance=tolerance,
                batch_size=1000,
            )
            if tolerance == TOLERANCES[0]:
                step_list = [
                    "generate_protected_areas_table",
                    "generate_terrestrial_biome_stats",
                    "generate_dissolved_terrestrial_pa",
                    "generate_eez_minus_mpa",
                ]

        # ------------------
        #   Table updates
        # ------------------

        case "generate_terrestrial_biome_stats":
            _ = generate_terrestrial_biome_stats_pa(verbose=verbose)
            step_list = ["generate_habitat_protection_table"]

        case "generate_habitat_protection_table":
            _ = generate_habitat_protection_table(verbose=verbose)
            step_list = ["update_habitat_protection_stats"]

        case "generate_protection_coverage_stats_table":
            _ = generate_protection_coverage_stats_table(verbose=verbose)
            step_list = ["update_protection_coverage_stats"]

        case "generate_marine_protection_level_stats_table":
            _ = generate_marine_protection_level_stats_table(verbose=verbose)
            step_list = ["update_mpaa_protection_level_stats"]

        case "generate_fishing_protection_table":
            _ = generate_fishing_protection_table(verbose=verbose)
            step_list = ["update_fishing_protection_stats"]

        case "generate_locations_table":
            generate_locations_table(verbose=verbose)
            step_list = ["update_locations"]

        case "generate_protected_areas_table":
            updates = generate_protected_areas_diff_table(verbose=verbose)
            if updates:
                step_list = ["update_protected_areas"]
                if env == "production":
                    step_list.extend(
                        [
                            "update_marine_protected_areas_tileset",
                            "update_terrestrial_protected_areas_tileset",
                        ]
                    )

        case "generate_dissolved_terrestrial_pa":
            dissolve_geometries(tolerance=tolerance, verbose=verbose)
            step_list = ["generate_gadm_minus_pa"]

        case "generate_gadm_minus_pa":
            generate_total_area_minus_pa(
                total_area_file=GADM_FILE_NAME,
                pa_file=DISSOLVED_TERRESTRIAL_PA,
                is_processed=True,
                out_file=CONSERVATION_BUILDER_TERRESTRIAL_DATA,
                tolerance=tolerance,
                verbose=verbose,
            )
            step_list = ["update_gadm_minus_pa"]

        case "generate_eez_minus_mpa":
            generate_total_area_minus_pa(
                total_area_file=EEZ_FILE_NAME,
                pa_file=WDPA_MARINE_FILE_NAME,
                is_processed=False,
                out_file=CONSERVATION_BUILDER_MARINE_DATA,
                tolerance=tolerance,
                verbose=verbose,
            )
            step_list = ["update_eez_minus_mpa"]

        # ------------------
        #   Database updates
        # ------------------

        case "update_locations":
            resp = upload_locations(request=data, verbose=verbose)
            return resp, retry_config

        case "update_protection_coverage_stats":
            client = Strapi()
            return upload_stats(
                filename=PROTECTION_COVERAGE_FILE_NAME,
                upload_function=client.upsert_protection_coverage_stats,
                verbose=verbose,
            ), retry_config

        case "update_mpaa_protection_level_stats":
            client = Strapi()
            return upload_stats(
                filename=PROTECTION_LEVEL_FILE_NAME,
                upload_function=client.upsert_mpaa_protection_level_stats,
                verbose=verbose,
            ), retry_config

        case "update_fishing_protection_stats":
            client = Strapi()
            return upload_stats(
                filename=FISHING_PROTECTION_FILE_NAME,
                upload_function=client.upsert_fishing_protection_level_stats,
                verbose=verbose,
            ), retry_config

        case "update_habitat_protection_stats":
            client = Strapi()
            return upload_stats(
                filename=HABITAT_PROTECTION_FILE_NAME,
                upload_function=client.upsert_habitat_stats,
                verbose=verbose,
            ), retry_config

        case "update_protected_areas":
            update_segment = data.get("UPDATE_SEGMENT", "all")
            upload_protected_areas(verbose=verbose, update_segment=update_segment)

        case "update_gadm_minus_pa":
            update_cb(
                table_name="gadm_minus_pa_v2",
                gcs_file=CONSERVATION_BUILDER_TERRESTRIAL_DATA,
                verbose=verbose,
            )

        case "update_eez_minus_mpa":
            update_cb(
                table_name="eez_minus_mpa_v2",
                gcs_file=CONSERVATION_BUILDER_MARINE_DATA,
                verbose=verbose,
            )

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
            logger.warning({"message": f"METHOD: {method} not a valid option"})

    if trigger_next and cont and step_list:
        pipe_next_steps(step_list, task_config, LONG_RUNNING_TASKS, verbose=verbose)

    return ("OK", 200), retry_config


def run_from_payload(data: dict, verbose: bool = True) -> tuple[str, int]:
    """
    Shared runner used by both Cloud Function and Cloud Run Job.
    Returns (message, status_code_like).
    """

    st = datetime.now()

    project = os.environ.get("PROJECT", "")
    env = os.environ.get("ENVIRONMENT", "")
    location = os.environ.get("LOCATION", "")
    webhook_url = os.environ.get("SLACK_ALERTS_WEBHOOK", "")
    method = data.get("METHOD", "dry_run")
    trigger_next = data.get("TRIGGER_NEXT", False)
    tolerance = data.get("TOLERANCE", TOLERANCES[0])
    max_retries = data.get("MAX_RETRIES", 0)
    attempt = data.get("attempt", 1)

    try:
        task_config = {
            "PROJECT": project,
            "LOCATION": location,
            "QUEUE_NAME": data.get("QUEUE_NAME", ""),
            "JOB_NAME": data.get("JOB_NAME", ""),
            "TARGET_URL": data.get("TARGET_URL", ""),
            "INVOKER_SA": data.get("INVOKER_SA", ""),
            "TOLERANCE": tolerance,
            "TRIGGER_NEXT": trigger_next,
            "MAX_RETRIES": max_retries,
            "attempt": attempt,
        }

        retry_config = {"delay_seconds": (attempt - 1) * 60, "max_retries": max_retries}

        logger.info({"message": f"Starting METHOD: {method}"})

        is_job = bool(os.environ.get("RUN_PAYLOAD"))
        if (not is_job) and method in LONG_RUNNING_TASKS:
            payload = {"METHOD": method, **task_config, **data}
            resp = long_running_tasks(payload, timeout=5, verbose=verbose)
            logger.info({"message": f"METHOD: {method} triggered as long-running task"})
            return resp

        # Normal (non-long-running) execution path
        resp, retry_config = dispatch_publisher(
            method,
            task_config,
            data,
            retry_config,
            trigger_next=trigger_next,
            env=env,
            tolerance=tolerance,
            verbose=verbose,
        )

        logger.info({"message": f"METHOD: {method} complete!"})
        return resp

    except Exception as e:
        retries = retry_config["max_retries"]
        if attempt < retries + 1:
            logger.warning(
                {
                    "message": f"METHOD {method} failed attempt {attempt}: {e} of {retries + 1}",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            task_config["attempt"] = attempt + 1
            payload = {"METHOD": method, **task_config}
            create_task(
                payload=payload, verbose=verbose, delay_seconds=retry_config["delay_seconds"]
            )
            return "retrying", 202
        else:
            logger.error(
                {
                    "message": f"METHOD {method} failed after {attempt} attempts",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            send_slack_alert(webhook_url, f"METHOD {method} failed on {env.upper()}")
            return f"METHOD {method} failed after {attempt} attempts: {e}", 208

    finally:
        release_memory(verbose=verbose)
        fn = datetime.now()
        logger.info(
            {"message": f"{method} Completed in {(fn - st).total_seconds() / 60:.2f} minutes"}
        )
