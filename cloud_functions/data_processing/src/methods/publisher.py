import json

from google.cloud import pubsub_v1


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
    jobs = [{"METHOD": "download_mpatlas"}]

    publish_jobs(jobs, project_id, topic_id, verbose)
