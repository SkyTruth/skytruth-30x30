import base64
import json
import signal

import functions_framework
from flask import Request

from src.methods.publisher import run_from_payload
from src.utils.resource_handling import handle_sigterm

# Register SIGTERM handler
signal.signal(signal.SIGTERM, handle_sigterm)


@functions_framework.http
def main(request: Request) -> tuple[str, int]:
    data = request.get_json(silent=True) or {}

    # in case received as a queue message
    if "message" in data:
        msg = data["message"]
        data_bytes = base64.b64decode(msg["data"])
        data = json.loads(data_bytes.decode("utf-8"))

    msg, code = run_from_payload(data)
    return msg, code
