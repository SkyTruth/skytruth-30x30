import gc
import os
import tracemalloc

import psutil
import pyarrow

from src.core.commons import send_slack_alert
from src.utils.logger import Logger

logger = Logger()


def show_mem(label: str = ""):
    """
    This reports the memory used by the current process — including
    Python objects, loaded shared libraries, and native memory allocations
    (e.g., from NumPy, GEOS, GDAL).

    Args:
        label (str, optional): A label to include in log

    """
    process = psutil.Process(os.getpid())
    rss = process.memory_info().rss / 1e6  # in MB
    print(f"[{label}] Memory: {rss:.1f} MB")


def show_container_mem(label: str = ""):
    """
    Print the current container memory usage (in MB) from cgroup metrics.

    Works for both cgroup v1 and v2:
    - /sys/fs/cgroup/memory/memory.usage_in_bytes  (v1)
    - /sys/fs/cgroup/memory.current                (v2)

    This reports the *total container memory use*, including native allocations,
    Arrow/GDAL buffers, page cache, and all processes inside the container.
    """
    usage_bytes = None

    # Try cgroup v1 path first
    v1_path = "/sys/fs/cgroup/memory/memory.usage_in_bytes"
    v2_path = "/sys/fs/cgroup/memory.current"

    try:
        with open(v1_path) as f:
            usage_bytes = int(f.read().strip())
    except FileNotFoundError:
        try:
            with open(v2_path) as f:
                usage_bytes = int(f.read().strip())
        except FileNotFoundError:
            print(f"[{label}] Could not read container memory usage.")
            return

    usage_gb = usage_bytes / 1e9
    print(f"[{label}] Container memory: {usage_gb:.1f} GB")


def print_peak_memory_allocation(func, *args, **kwargs):
    tracemalloc.start()
    try:
        out = func(*args, **kwargs)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    print(f"max allocated memory: {peak / (1024**3):.3f} GB")
    return out


def release_memory(verbose=True):
    """
    Free up memory
    """
    # Run garbage collector
    gc.collect()

    # Release any unused memory back to the OS, ensuring that
    # large Arrow buffers (e.g., from Parquet I/O) are freed.
    pyarrow.default_memory_pool().release_unused()

    # log memory allocation after releasing memory
    if verbose:
        show_container_mem("Container memory after releasing memory")


def handle_sigterm(signum, frame):
    """
    Handle the SIGTERM signal.
    """
    # Log an error-level message noting that a SIGTERM was received.
    logger.error(
        {
            "message": "SIGTERM signal received",
            "file_name": frame.f_code.co_filename,
            "line_number": frame.f_lineno,
        }
    )

    webhook_url = os.environ.get("SLACK_ALERTS_WEBHOOK", "")
    send_slack_alert(webhook_url, "TIMEOUT ERROR - SIGTERM signal received")

    # Free up memory
    release_memory()
