import json
from datetime import UTC, datetime, timedelta

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from src.utils.logger import Logger

logger = Logger()


def create_task(
    payload: dict,
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
            print(f"Created task: {response.name}")
        return response
    except Exception as e:
        logger.error({"message": f"Error creating Cloud Task: {e}"})
        raise


def monthly_job_publisher(task_config, verbose=True):
    """Enqueue the 4–5 monthly tasks into Cloud Tasks."""

    jobs = [
        {
            "METHOD": "test_retries",
            **task_config,
        },
        # {
        #     "METHOD": "download_mpatlas",
        #     **task_config,
        # },
        # {
        #     "METHOD": "download_protected_seas",
        #     **task_config,
        # },
        # {
        #     "METHOD": "download_protected_planet_country",
        #     **task_config,
        # },
        {
            "METHOD": "download_protected_planet_pas",
            "TOLERANCE": 0.001,
            **task_config,
        },
    ]

    # for tolerance in TOLERANCES:
    #     jobs.append(
    #         {
    #             "METHOD": "download_protected_planet_pas",
    #             "TOLERANCE": tolerance,
    #             **task_config,
    #         }
    #     )

    for job in jobs:
        create_task(payload=job, verbose=verbose)


def launch_next_step(
    next_method: str,
    task_config: dict,
    verbose: bool = True,
):
    """Enqueue exactly one downstream task."""

    payload = {"METHOD": next_method, **task_config}

    if verbose:
        print(f"Launching next step: {next_method}")

    create_task(payload=payload, verbose=verbose)


def pipe_next_steps(
    step_list: list,
    trigger_next: bool,
    task_config: dict,
    verbose: bool = True,
):
    """Enqueue a sequence of downstream steps."""

    if trigger_next:
        for next_method in step_list:
            launch_next_step(
                next_method,
                task_config,
                verbose=verbose,
            )
