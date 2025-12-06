import json
from datetime import UTC, datetime, timedelta

import requests
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from src.utils.logger import Logger

logger = Logger()


def long_running_tasks(payload, timeout=1, verbose=True):
    if verbose:
        method = payload.get("METHOD", "")
        logger.info(
            {"message": f"Launching Long-Running Cloudfunction: {method}: {json.dumps(payload)}"}
        )
    try:
        requests.post(payload["TARGET_URL"], json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        pass
    except Exception as e:
        logger.error({"message": "Error triggering long-running CF", "error": str(e)})

    return ("OK", 200)


def create_task(
    payload,
    delay_seconds: int | None = None,
    verbose: bool = True,
):
    """Create a single Cloud Task to POST JSON to a Cloud Function."""

    project_id = payload["PROJECT"]
    location = payload["LOCATION"]
    queue = payload["QUEUE_NAME"]
    target_url = payload["TARGET_URL"]
    service_account_email = payload["INVOKER_SA"]

    client = tasks_v2.CloudTasksClient()

    parent = client.queue_path(project_id, location, queue)

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
            "METHOD": "generate_protected_areas_table",
            **task_config,
        }
    ]

    # jobs = [
    #     {
    #         "METHOD": "download_mpatlas",
    #         **task_config,
    #     },
    #     {
    #         "METHOD": "download_protected_seas",
    #         **task_config,
    #     },
    #     {
    #         "METHOD": "download_protected_planet_country",
    #         **task_config,
    #     },
    # ]

    # for tolerance in TOLERANCES:
    #     jobs.append(
    #         {
    #             "METHOD": "download_protected_planet_pas",
    #             "TOLERANCE": tolerance,
    #             **task_config,
    #         }
    #     )

    for job in jobs:
        if long_running_task_list and job["METHOD"] in long_running_task_list:
            create_task(job, verbose=verbose)
        else:
            long_running_tasks(job, verbose=verbose)


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
