"""Optional daily receipts at successful shared-dataset consumption boundaries."""
import os

_PRODUCERS = {
    "x30-prod-data": "thirty-by-thirty-production",
    "x30-dev-data": "thirty-by-thirty-development"
}
_reporter = None


def record_dataset_use(slug):
    global _reporter
    if os.environ.get("DATASET_USAGE_ENABLED") == "false":
        return
    producer = _PRODUCERS.get(os.environ.get("K_SERVICE"))
    if not producer:
        return
    if _reporter is None:
        from skytruth_shared_datasets import UsageReporter
        _reporter = UsageReporter(producer)
    _reporter.recordUsage(slug, "use")
    _reporter.flush()
