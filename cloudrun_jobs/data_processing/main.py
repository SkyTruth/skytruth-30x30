import json
import os
import sys
import signal

from src.methods.publisher import run_from_payload
from src.utils.resource_handling import handle_sigterm

signal.signal(signal.SIGTERM, handle_sigterm)

def main() -> int:
    raw = os.environ.get("RUN_PAYLOAD", "")
    if not raw:
        # You could support PAYLOAD_GCS_URI later if needed
        print("Missing RUN_PAYLOAD env var")
        return 2

    data = json.loads(raw)
    _, code = run_from_payload(data)

    if code in (200, 202):
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
