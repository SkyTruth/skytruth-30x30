ONE_MINUTE = 60
ONE_HOUR = 60 * ONE_MINUTE
ONE_DAY = 24 * ONE_HOUR


def default_delay(attempt: int) -> int:
    """Backoff delay for generic retries: (attempt - 1) * 1 minute."""
    return (attempt - 1) * ONE_MINUTE


DEFAULT_RETRY_CONFIG = {
    "delay_seconds": default_delay,
    "max_retries": 0,
}

METHOD_RETRY_CONFIGS = {
    "download_mpatlas": {
        "delay_seconds": ONE_DAY,
        "max_retries": 3,
    },
    "download_protected_planet_pas": {
        "delay_seconds": ONE_DAY,
        "max_retries": 7,
    },
    "update_marine_protected_areas_tileset": {
        "delay_seconds": ONE_HOUR,
        "max_retries": 3,
    },
    "update_terrestrial_protected_areas_tileset": {
        "delay_seconds": ONE_HOUR,
        "max_retries": 3,
    },
    "update_mpatlas_tileset": {
        "delay_seconds": ONE_HOUR,
        "max_retries": 3,
    },
}


class ScheduleRetry(Exception):
    """Raised when a method fails and should be retried on a delay.

    Caught by run_from_payload to schedule a Cloud Task retry.
    """

    def __init__(self, delay_seconds: int, max_retries: int, message: str = ""):
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        super().__init__(
            message or f"Retry requested: {max_retries} retries, {delay_seconds}s delay"
        )
