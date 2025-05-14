"""Logger class to write logs to GCP logging service"""

import json
import os


class Logger:
    """Logger class to write logs to GCP logging service"""

    def __init__(self, request=None):
        self.project = os.environ.get("PROJECT")
        self.request = request

    def _format_structured_payload(self, payload: dict) -> dict:
        """Format the payload to be sent to GCP logging service"""
        global_log_fields = {}

        # Add log correlation to nest all log messages.
        # This is only relevant in HTTP-based contexts, and is ignored elsewhere.
        # (In particular, non-HTTP-based Cloud Functions.)
        if self.request:
            trace_header = self.request.headers.get("X-Cloud-Trace-Context")

            if trace_header and self.project:
                trace = trace_header.split("/")
                global_log_fields["logging.googleapis.com/trace"] = (
                    f"projects/{self.project}/traces/{trace[0]}"
                )

        return dict(
            **payload,
            **global_log_fields,
        )

    def info(self, payload: dict) -> None:
        """Log an info message to GCP logging service"""
        payload = self._format_structured_payload(payload)
        payload["severity"] = "INFO"
        self.log(payload)

    def warning(self, payload: dict) -> None:
        """Log a warning message to GCP logging service"""
        payload = self._format_structured_payload(payload)
        payload["severity"] = "WARNING"

    def error(self, payload: dict) -> None:
        """Log an error message to GCP logging service"""
        payload = self._format_structured_payload(payload)
        payload["severity"] = "ERROR"
        self.log(payload)

    def log(self, payload: dict) -> None:
        """Log a message to GCP logging service"""
        print(json.dumps(payload))
