import json

from google.cloud import pubsub_v1

from src.utils.logger import Logger

logger = Logger()


def publish_jobs(jobs, project_id, topic_id, verbose):
    """Publish job messages to a Pub/Sub topic."""

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)

    for job in jobs:
        message_data = json.dumps(job).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        if verbose:
            print(f"Published message ID: {future.result()}")


def monthly_job_publisher(project_id, topic_id, verbose=True):
    # Define jobs to queue — each will trigger your Cloud Function or Cloud Run worker
    jobs = [
        {"METHOD": "test_dead_letter"}
        # {"METHOD": "download_mpatlas"},
        # {"METHOD": "download_protected_seas"},
        # {"METHOD": "download_protected_planet_country"},
        # {"METHOD": "download_protected_planet_pas", "TOLERANCE": 0.001},
        # {"METHOD": "download_protected_planet_pas", "TOLERANCE": 0.0001},
    ]

    publish_jobs(jobs, project_id, topic_id, verbose)


def launch_next_step(next_method, project_id, topic_id, verbose=True):
    if topic_id is not None:
        try:
            if verbose:
                print(f"launching method: {next_method}")
            jobs = [{"METHOD": next_method, "PROJECT": project_id, "TOPIC": topic_id}]
            publish_jobs(jobs, project_id, topic_id, verbose)
        except Exception as e:
            logger.error({"message": f"Error invoking {next_method}: {e}"})
