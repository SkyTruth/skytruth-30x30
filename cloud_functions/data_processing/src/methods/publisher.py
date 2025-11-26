import json
from google.cloud import tasks_v2

from src.utils.logger import Logger

logger = Logger()


# def publish_jobs(jobs, project_id, topic_id, verbose):
#     """Publish job messages to a Pub/Sub topic."""

#     publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
#     publisher = pubsub_v1.PublisherClient(publisher_options=publisher_options)
#     topic_path = publisher.topic_path(project_id, topic_id)

#     for job in jobs:
#         message_data = json.dumps(job).encode("utf-8")
#         future = publisher.publish(topic_path, message_data, ordering_key="default")
#         if verbose:
#             print(f"Published message ID: {future.result()}")


# def monthly_job_publisher(project_id, topic_id, verbose=True):
#     # Define jobs to queue — each will trigger your Cloud Function or Cloud Run worker
#     try:
#         jobs = [
#             {
#                 "METHOD": "download_mpatlas",
#                 "PROJECT": project_id,
#                 "TOPIC": topic_id,
#                 "TRIGGER_NEXT": True,
#             },
#             {
#                 "METHOD": "download_protected_seas",
#                 "PROJECT": project_id,
#                 "TOPIC": topic_id,
#                 "TRIGGER_NEXT": True,
#             },
#             {
#                 "METHOD": "download_protected_planet_country",
#                 "PROJECT": project_id,
#                 "TOPIC": topic_id,
#                 "TRIGGER_NEXT": True,
#             },
#             {
#                 "METHOD": "download_protected_planet_pas",
#                 "TOLERANCE": 0.001,
#                 "PROJECT": project_id,
#                 "TOPIC": topic_id,
#                 "TRIGGER_NEXT": True,
#             },
#             {
#                 "METHOD": "download_protected_planet_pas",
#                 "TOLERANCE": 0.0001,
#                 "PROJECT": project_id,
#                 "TOPIC": topic_id,
#                 "TRIGGER_NEXT": True,
#             },
#         ]

#         publish_jobs(jobs, project_id, topic_id, verbose)
#     except Exception as e:
#         logger.error({"message": f"Error invoking monthly publisher: {e}"})


# def launch_next_step(next_method, project_id, topic_id, verbose=True):
#     if topic_id is not None:
#         try:
#             if verbose:
#                 print(f"launching method: {next_method}")
#             jobs = [
#                 {
#                     "METHOD": next_method,
#                     "PROJECT": project_id,
#                     "TOPIC": topic_id,
#                     "TRIGGER_NEXT": True,
#                 }
#             ]
#             publish_jobs(jobs, project_id, topic_id, verbose)
#         except Exception as e:
#             logger.error({"message": f"Error invoking {next_method}: {e}"})


# def pipe_next_steps(
#     step_list: list, trigger_next: bool, project_id: str, topic_id: str, verbose: bool = True
# ):
#     if trigger_next:
#         for next_method in step_list:
#             launch_next_step(next_method, project_id, topic_id, verbose=verbose)


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
            "oidc_token": {
                "service_account_email": service_account_email
            },
        }
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
            "PROJECT": task_config["project_id"],
            "TRIGGER_NEXT": True,
        },
        {
            "METHOD": "download_protected_seas",
            "PROJECT": task_config["project_id"],
            "TRIGGER_NEXT": True,
        },
        {
            "METHOD": "download_protected_planet_country",
            "PROJECT": task_config["project_id"],
            "TRIGGER_NEXT": True,
        },
        {
            "METHOD": "download_protected_planet_pas",
            "TOLERANCE": 0.001,
            "PROJECT": task_config["project_id"],
            "TRIGGER_NEXT": True,
        },
        {
            "METHOD": "download_protected_planet_pas",
            "TOLERANCE": 0.0001,
            "PROJECT": task_config["project_id"],
            "TRIGGER_NEXT": True,
        },
    ]

    for job in jobs:
        create_task(
            project_id=task_config["project_id"],
            location=task_config["location"],
            queue=task_config["queue_name"],
            target_url=task_config["target_url"],
            service_account_email=task_config["service_account_email"],
            payload=job,
            verbose=verbose,
        )


def launch_next_step(
    next_method: str,
    project_id: str,
    location: str,
    queue_name: str,
    target_url: str,
    service_account_email: str,
    verbose: bool = True,
):
    """Enqueue exactly one downstream task."""

    payload = {
        "METHOD": next_method,
        "PROJECT": project_id,
        "TRIGGER_NEXT": True,
    }

    if verbose:
        print(f"Launching next step: {next_method}")

    create_task(
        project_id=project_id,
        location=location,
        queue=queue_name,
        target_url=target_url,
        service_account_email=service_account_email,
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
                task_config["project_id"],
                task_config["location"],
                task_config["queue_name"],
                task_config["target_url"],
                task_config["service_account_email"],
                verbose=verbose,
            )

