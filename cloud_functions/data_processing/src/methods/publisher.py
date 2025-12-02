import json

from google.cloud import tasks_v2

from src.core.params import TOLERANCES
from src.utils.logger import Logger

logger = Logger()


def create_task(
    project_id: str,
    location: str,
    queue: str,
    target_url: str,
    service_account_email: str,
    payload: dict,
    verbose: bool = True,
):
    """Create a single Cloud Task to POST JSON to a Cloud Function."""

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
                "TOLERANCE": tolerance,
                **task_config,
            }
        )

    for job in jobs:
        create_task(
            project_id=task_config["PROJECT"],
            location=task_config["LOCATION"],
            queue=task_config["QUEUE_NAME"],
            target_url=task_config["TARGET_URL"],
            service_account_email=task_config["INVOKER_SA"],
            payload=job,
            verbose=verbose,
        )


def launch_next_step(
    next_method: str,
    task_config: dict,
    verbose: bool = True,
):
    """Enqueue exactly one downstream task."""

    payload = {"METHOD": next_method, **task_config}

    if verbose:
        print(f"Launching next step: {next_method}")

    create_task(
        project_id=task_config["PROJECT"],
        location=task_config["LOCATION"],
        queue=task_config["QUEUE_NAME"],
        target_url=task_config["TARGET_URL"],
        service_account_email=task_config["INVOKER_SA"],
        payload=payload,
        verbose=verbose,
    )


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
