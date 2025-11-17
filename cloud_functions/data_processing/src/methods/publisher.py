import json
import os

from google.cloud import pubsub_v1


def publish_jobs(jobs):
    """Publish job messages to a Pub/Sub topic."""
    project_id = os.environ["GCP_PROJECT"]
    topic_id = "job-topic"

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)

    for job in jobs:
        message_data = json.dumps(job).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        print(f"Published message ID: {future.result()}")


def monthly_job_publisher():
    # Define jobs to queue — each will trigger your Cloud Function or Cloud Run worker
    jobs = [{"METHOD": "download_mpatlas"}]

    publish_jobs(jobs)
