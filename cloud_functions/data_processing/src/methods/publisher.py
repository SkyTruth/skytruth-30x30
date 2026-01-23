import json
from datetime import UTC, datetime, timedelta

from google.api_core import exceptions as gax_exceptions
from google.cloud import run_v2, tasks_v2
from google.protobuf import timestamp_pb2

from src.core.params import TOLERANCES
from src.utils.logger import Logger

logger = Logger()


# def long_running_tasks(payload, timeout=1, verbose=True):
#     if verbose:
#         method = payload.get("METHOD", "")
#         logger.info(
#             {"message": f"Launching Long-Running Cloudfunction: {method}: {json.dumps(payload)}"}
#         )
#     try:
#         requests.post(payload["TARGET_URL"], json=payload, timeout=timeout)
#     except requests.exceptions.Timeout:
#         pass
#     except Exception as e:
#         logger.error({"message": "Error triggering long-running CF", "error": str(e)})

#     return ("OK", 200)


def long_running_tasks(payload, timeout=5, verbose=True):
    if verbose:
        method = payload.get("METHOD", "")
        logger.info(
            {"message": f"Launching Long-Running Cloudfunction: {method}: {json.dumps(payload)}"}
        )

    client = run_v2.JobsClient()

    project_id = payload.get("PROJECT_ID")
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
                        run_v2.EnvVar(name="PAYLOAD", value=run_payload),
                        run_v2.EnvVar(name="METHOD", value=payload.get("METHOD", "")),
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
