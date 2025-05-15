"""Logger class to write logs to GCP logging service"""

import json
import os


class Logger:
    """Logger class to write logs to GCP logging service"""

    def __init__(self, request=None):
        self.project = os.environ.get("PROJECT")
        self.request = request

    def info(self, payload: dict) -> None:
        """Log an info message to GCP logging service"""
        payload["severity"] = "INFO"
        self.log(payload)

    def warning(self, payload: dict) -> None:
        """Log a warning message to GCP logging service"""
        payload["severity"] = "WARNING"
        self.log(payload)

    def error(self, payload: dict) -> None:
        """Log an error message to GCP logging service"""
        payload["severity"] = "ERROR"
        self.log(payload)

    def log(self, payload: dict) -> None:
        """Log a message to GCP logging service"""
        print(json.dumps(payload))
