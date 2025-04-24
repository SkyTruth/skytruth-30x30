# from rasterstats import zonal_stats
# from exactextract import exact_extract  # in the future i need to explore this further
import numpy as np
import rasterio as rio
from rasterio.windows import Window
# from shapely.geometry import box
from pathlib import Path
from typing import List, Iterable
from logging import getLogger
from itertools import product
from dask.distributed import wait, Lock
import dask.delayed

from v2.datasets import RasterDataset

logger = getLogger(__name__)


def window_generator(
    width: int, height: int, window_size_x: int, window_size_y: None | int = None
) -> Iterable[Window]:  # this is something to be rethink within the grid generator
    """
    Generate windows of a given size for a raster of specified width and height.

    Parameters:
    width (int): Width of the raster.
    height (int): Height of the raster.
    window_size (int): Size of the window (assumes square windows).

    Yields:
    tuple: A tuple representing the window (row_start, row_stop, col_start, col_stop).
    """
    if window_size_y is None:
        window_size_y = window_size_x

    for row_i, col_j in product(
        np.arange(0, width, window_size_x), np.arange(0, height, window_size_y)
    ):

        _w = window_size_x
        _h = window_size_y

        if row_i + window_size_x > width:
            _w = width - row_i
        if col_j + window_size_y > height:
            _h = height - col_j

        yield Window(row_i, col_j, _w, _h)


def process_job_chunk(
    src_raster: RasterDataset,
    dst_raster: RasterDataset | None,
    window: Window | None,
    process_func: callable,
    lock: Lock | None = None,
    *f_args,
    **f_kwargs,
):
    status_message = {
        "diagnostics": {},
        "messages": [f"Processing chunk: {window}"],
        "return_val": None,
    }
    # read the chunk
    try:
        status_message["messages"].append("reading data")
        data = src_raster.read(window=window)
        status_message["messages"].append("processing data")
        result = process_func(data, *f_args, **f_kwargs)
        if dst_raster:
            status_message["messages"].append("writing data")
            if lock:
                with lock:
                    dst_raster.write(result, window=window)
            else:
                dst_raster.write(result, window=window)
        else:
            status_message["return_val"] = result

        status_message["messages"].append("success in processing chunk")

    except Exception as e:
        status_message["diagnostics"]["error"] = e
    finally:
        return status_message


def is_single_dataset(args):
    if isinstance(args, Path):
        return RasterDataset(args)
    elif isinstance(args, str):
        return RasterDataset(Path(args))
    elif isinstance(args, list):
        # TODO create a virtual raster from the list of rasters
        raise NotImplementedError("List of rasters not yet supported")
    else:
        raise ValueError("Invalid input data type")


def process_raster(
    in_data: List[Path] | Path,
    out_data: Path | None,
    out_data_profile: dict | None,
    process_func: callable,
    f_kwargs: dict = {},
    dask_client=None,
    window_size=1000,
):
    """
    Process a raster dataset using a given function.

    Parameters:
    in_data (Path|List[Path]): The input raster dataset(s).
    out_data (Path): The output raster dataset.
    process_func (callable): The function to apply to the raster data.
    f_kwargs (dict): The keyword arguments to pass to the function.
    dask_client (dask.distributed.Client): The dask client to use for parallel processing.
    window_size (int): The size of the processing window.

    Returns:
    list: A list of results from the processing function

    """
    with rio.Env():
        raster_input = is_single_dataset(in_data)
        raster_output = None

        if out_data:
            new_profile = raster_input.profile.copy()
            new_profile.update(**out_data_profile) if out_data_profile else None
            raster_output = RasterDataset(out_data, profile=new_profile)

        window_chunks = window_generator(
            raster_input.profile.get("width"), raster_input.profile.get("height"), window_size
        )

        # Process the data in parallel usind dask distributed
        if dask_client:
            # doing it with futures
            if (
                raster_output is not None
            ):  # to avoid writing to the same file at the same time that will cause an error we need a lock
                print("Processing in parallel with lock")
                lc = Lock()
                tasks = [
                    dask_client.submit(
                        process_job_chunk,
                        raster_input,
                        raster_output,
                        window,
                        process_func,
                        lc,
                        **f_kwargs,
                    )
                    for window in window_chunks
                ]
                futures = dask_client.gather(tasks)

                result = wait(futures)

                return futures, result
            else:
                print("Processing in parallel without lock")
                tasks = [
                    dask.delayed(process_job_chunk)(
                        raster_input, raster_output, window, process_func, None, **f_kwargs
                    )
                    for window in window_chunks
                ]
                futures = dask_client.compute(tasks, sync=False)

                for future, result in dask.distributed.as_completed(futures, with_results=True):
                    future.release()
                    yield result

                return futures

        else:
            # to process it in serial

            serial_results = [
                process_job_chunk(raster_input, raster_output, window, process_func, **f_kwargs)
                for window in window_chunks
            ]

            return serial_results
