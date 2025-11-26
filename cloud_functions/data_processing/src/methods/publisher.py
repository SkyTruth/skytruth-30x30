import json

from google.cloud import pubsub_v1

from src.utils.logger import Logger

logger = Logger()


def publish_jobs(jobs, project_id, topic_id, verbose):
    """Publish job messages to a Pub/Sub topic."""

    publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
    publisher = pubsub_v1.PublisherClient(publisher_options=publisher_options)
    topic_path = publisher.topic_path(project_id, topic_id)

    for job in jobs:
        message_data = json.dumps(job).encode("utf-8")
        future = publisher.publish(topic_path, message_data, ordering_key="default")
        if verbose:
            print(f"Published message ID: {future.result()}")


def monthly_job_publisher(project_id, topic_id, verbose=True):
    # Define jobs to queue — each will trigger your Cloud Function or Cloud Run worker
    try:
        jobs = [
            {
                "METHOD": "download_mpatlas",
                "PROJECT": project_id,
                "TOPIC": topic_id,
                "TRIGGER_NEXT": True,
            },
            {
                "METHOD": "download_protected_seas",
                "PROJECT": project_id,
                "TOPIC": topic_id,
                "TRIGGER_NEXT": True,
            },
            {
                "METHOD": "download_protected_planet_country",
                "PROJECT": project_id,
                "TOPIC": topic_id,
                "TRIGGER_NEXT": True,
            },
            {
                "METHOD": "download_protected_planet_pas",
                "TOLERANCE": 0.001,
                "PROJECT": project_id,
                "TOPIC": topic_id,
                "TRIGGER_NEXT": True,
            },
            {
                "METHOD": "download_protected_planet_pas",
                "TOLERANCE": 0.0001,
                "PROJECT": project_id,
                "TOPIC": topic_id,
                "TRIGGER_NEXT": True,
            },
        ]

        publish_jobs(jobs, project_id, topic_id, verbose)
    except Exception as e:
        logger.error({"message": f"Error invoking monthly publisher: {e}"})


def launch_next_step(next_method, project_id, topic_id, verbose=True):
    if topic_id is not None:
        try:
            if verbose:
                print(f"launching method: {next_method}")
            jobs = [
                {
                    "METHOD": next_method,
                    "PROJECT": project_id,
                    "TOPIC": topic_id,
                    "TRIGGER_NEXT": True,
                }
            ]
            publish_jobs(jobs, project_id, topic_id, verbose)
        except Exception as e:
            logger.error({"message": f"Error invoking {next_method}: {e}"})


def pipe_next_steps(
    step_list: list, trigger_next: bool, project_id: str, topic_id: str, verbose: bool = True
):
    if trigger_next:
        for next_method in step_list:
            launch_next_step(next_method, project_id, topic_id, verbose=verbose)
