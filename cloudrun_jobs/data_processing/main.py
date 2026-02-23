import json
import os
import sys
import signal
import traceback

from src.methods.publisher import run_from_payload
from src.utils.logger import Logger
from src.utils.resource_handling import handle_sigterm

logger = Logger()

signal.signal(signal.SIGTERM, handle_sigterm)


def main() -> int:
    try:
        raw = os.environ.get("RUN_PAYLOAD", "")
        if not raw:
            logger.error({"message": "Missing RUN_PAYLOAD env var"})
            return 3

        try:
            data = json.loads(raw)
        except Exception as e:
            logger.error(
                {
                    "message": "Invalid RUN_PAYLOAD JSON",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            return 3

        result = run_from_payload(data)
        method = data.get("METHOD", "UNKNOWN")

        # Ensure correct shape
        if not isinstance(result, tuple) or len(result) != 2:
            logger.error(
                {
                    "message": "run_from_payload returned invalid response shape",
                    "type": type(result).__name__,
                    "value": repr(result),
                    "method": method
                }
            )
            return 71

        msg, code = result

        if code in (200, 202):
            return 0
        return 71

    except Exception as e:
        logger.error(
            {
                "message": "Unhandled exception in Cloud Run Job main",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "method": method
            }
        )
        return 71

if __name__ == "__main__":
    sys.exit(main())
