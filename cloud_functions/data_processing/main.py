import base64
import json
import signal
import traceback

import functions_framework
from flask import Request

from src.methods.publisher import run_from_payload
from src.utils.resource_handling import handle_sigterm

from src.utils.logger import Logger

logger = Logger()

# Register SIGTERM handler
signal.signal(signal.SIGTERM, handle_sigterm)


@functions_framework.http

def main(request: Request) -> tuple[str, int]:
    try:
        data = request.get_json(silent=True) or {}
        method = data.get("METHOD", "UNKNOWN")

        # In case received as a Pub/Sub push message
        if "message" in data:
            msg = data["message"]
            data_bytes = base64.b64decode(msg["data"])
            data = json.loads(data_bytes.decode("utf-8"))

        msg, code = run_from_payload(data)
        return msg, code

    except Exception as e:
        # Log full traceback
        logger.error(
            {
                "message": "Unhandled exception in main",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "method": method
            }
        )
        return "Internal Server Error", 500
